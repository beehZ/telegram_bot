import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from goal_system.discipline_keyboards import reminder_kb, delay_options_kb, quick_complete_kb

logger = logging.getLogger("reminder_engine")

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

STRICT_THRESHOLD_DELAYS = 3


class ReminderEngine:
    def __init__(self, db, bot, discipline_engine, finance_engine=None):
        self.db = db
        self.bot = bot
        self.disc_engine = discipline_engine
        self.finance_engine = finance_engine
        self.scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)
        self.sent_reminders: set[str] = set()
        self.followup_tracker: dict[str, int] = {}
        self.task_tracker = None

    def set_task_tracker(self, tracker):
        self.task_tracker = tracker

    def start(self):
        self.scheduler.start()
        logger.info("Discipline reminder engine started")

    async def stop(self):
        self.scheduler.shutdown(wait=False)

    def schedule_minute_check(self):
        now = datetime.now(TASHKENT_TZ)
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        trigger = DateTrigger(run_date=next_minute)
        self.scheduler.add_job(
            self._check_reminders,
            trigger,
            id="discipline_minute_check",
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info("Minute check scheduled for %s", next_minute.strftime("%H:%M"))

    def schedule_night_review(self, hour: int = 21, minute: int = 0):
        self.scheduler.add_job(
            self._night_review_all,
            CronTrigger(hour=hour, minute=minute, timezone=TASHKENT_TZ),
            id="night_review",
            replace_existing=True,
        )
        logger.info("Night review scheduled for %02d:%02d", hour, minute)

    async def _check_reminders(self):
        try:
            now = datetime.now(TASHKENT_TZ)
            routines = await self.disc_engine.get_tasks_for_time(now.hour, now.minute)

            for routine in routines:
                uid = routine["user_id"]
                rid = routine["id"]
                today = now.strftime("%Y-%m-%d")
                key = f"{uid}_{rid}_{today}"

                if key in self.sent_reminders:
                    continue

                # Smart reminder skip: check if manually completed or actively running
                if self.task_tracker:
                    already_done = await self.task_tracker.check_completed_before_reminder(uid, rid, today)
                    if already_done:
                        logger.info("Skipping reminder for routine %d (already completed/active)", rid)
                        self.sent_reminders.add(key)
                        continue

                existing = await self.db.fetchone(
                    "SELECT id FROM task_logs WHERE user_id = ? AND routine_id = ? AND date = ? AND status != 'pending'",
                    (uid, rid, today),
                )
                if existing:
                    continue

                lang = routine.get("language", "uz")
                text = self.disc_engine.build_reminder_text(routine, lang)
                kb = reminder_kb(rid)

                try:
                    await self.bot.send_message(uid, text, reply_markup=kb)
                    self.sent_reminders.add(key)
                    logger.info("Sent reminder for routine %d to user %d", rid, uid)

                    followup_key = f"followup_{key}"
                    self.scheduler.add_job(
                        self._send_followup,
                        DateTrigger(run_date=now + timedelta(minutes=15)),
                        args=[uid, rid, routine, lang],
                        id=f"followup_{key}",
                        replace_existing=True,
                    )
                except Exception as e:
                    logger.warning("Failed to send reminder to %d: %s", uid, e)

        except Exception as e:
            logger.exception("Reminder check failed: %s", e)

        self.schedule_next_check()

    def schedule_next_check(self):
        now = datetime.now(TASHKENT_TZ)
        next_minute = now + timedelta(minutes=1)
        self.scheduler.add_job(
            self._check_reminders,
            DateTrigger(run_date=next_minute.replace(second=0)),
            id="discipline_minute_check",
            replace_existing=True,
        )

    async def _send_followup(self, uid: int, rid: int, routine: dict, lang: str):
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        key = f"{uid}_{rid}_{today}"

        if self.task_tracker:
            already_done = await self.task_tracker.check_completed_before_reminder(uid, rid, today)
            if already_done:
                return

        existing = await self.db.fetchone(
            "SELECT id FROM task_logs WHERE user_id = ? AND routine_id = ? AND date = ? AND status != 'pending'",
            (uid, rid, today),
        )
        if existing:
            return

        disc = await self.db.get_discipline(uid)
        delay_count = disc["total_delayed"]
        strict_mode = delay_count > STRICT_THRESHOLD_DELAYS

        strict_labels = {
            "uz": "🚨 Vazifa hali bajarilmagan! Intizomingiz pasaymoqda. Hozir boshlang, 15 daqiqa ham natija.",
            "ru": "🚨 Задача еще не выполнена! Дисциплина падает. Начните сейчас, даже 15 минут — это прогресс.",
            "en": "🚨 Task still incomplete! Your discipline is dropping. Start now, even 15 minutes counts.",
        }
        normal_labels = {
            "uz": "⏰ Eslatma: vazifani hali bajarmadingiz. Bugun qilishga vaqt topasizmi?",
            "ru": "⏰ Напоминание: вы еще не выполнили задачу. Найдете время сегодня?",
            "en": "⏰ Reminder: you haven't completed this task yet. Can you make time today?",
        }

        text = strict_labels.get(lang, strict_labels["en"]) if strict_mode else normal_labels.get(lang, normal_labels["en"])
        kb = quick_complete_kb(rid)

        try:
            await self.bot.send_message(uid, text, reply_markup=kb)
            self.followup_tracker[key] = self.followup_tracker.get(key, 0) + 1
        except Exception as e:
            logger.warning("Failed to send followup to %d: %s", uid, e)

    async def handle_complete(self, uid: int, routine_id: int):
        result = await self.disc_engine.log_task_completion(uid, routine_id, "completed")
        lang = await self.db.get_language(uid)
        text = self.disc_engine.build_motivation_text(result, "completed", lang)
        return text

    async def handle_partial(self, uid: int, routine_id: int):
        result = await self.disc_engine.log_task_completion(uid, routine_id, "partial")
        lang = await self.db.get_language(uid)
        text = self.disc_engine.build_motivation_text(result, "partial", lang)
        return text

    async def handle_skip(self, uid: int, routine_id: int):
        result = await self.disc_engine.log_task_completion(uid, routine_id, "skipped")
        lang = await self.db.get_language(uid)
        text = self.disc_engine.build_motivation_text(result, "skipped", lang)
        return text

    async def handle_delay_request(self, uid: int, routine_id: int):
        lang = await self.db.get_language(uid)
        labels = {
            "uz": "Qancha vaqtga kechiktirmoqchisiz?",
            "ru": "На сколько отложить?",
            "en": "How long would you like to delay?",
        }
        return labels.get(lang, labels["en"]), delay_options_kb(routine_id)

    async def handle_delay_set(self, uid: int, routine_id: int, minutes: int):
        now = datetime.now(TASHKENT_TZ)
        new_time = now + timedelta(minutes=minutes)
        await self.disc_engine.log_task_completion(uid, routine_id, "delayed")

        lang = await self.db.get_language(uid)
        labels = {
            "uz": f"⏰ Vazifa {minutes} daqiqaga kechiktirildi. {new_time.strftime('%H:%M')} da eslataman.",
            "ru": f"⏰ Задача отложена на {minutes} мин. Напомню в {new_time.strftime('%H:%M')}.",
            "en": f"⏰ Task delayed by {minutes} min. I'll remind you at {new_time.strftime('%H:%M')}.",
        }

        routine = await self.db.get_routine(routine_id)
        kb = quick_complete_kb(routine_id)

        self.scheduler.add_job(
            self._send_delayed_reminder,
            DateTrigger(run_date=new_time),
            args=[uid, routine_id, routine, lang],
            id=f"delayed_{uid}_{routine_id}",
            replace_existing=True,
        )

        return labels.get(lang, labels["en"]), kb

    async def _send_delayed_reminder(self, uid: int, routine_id: int, routine: dict, lang: str):
        if not routine:
            return
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")

        if self.task_tracker:
            already_done = await self.task_tracker.check_completed_before_reminder(uid, routine_id, today)
            if already_done:
                return

        existing = await self.db.fetchone(
            "SELECT id FROM task_logs WHERE user_id = ? AND routine_id = ? AND date = ? AND status IN ('completed','partial','skipped')",
            (uid, routine_id, today),
        )
        if existing:
            return

        disc = await self.db.get_discipline(uid)
        delay_count = disc["total_delayed"]
        strict_mode = delay_count > STRICT_THRESHOLD_DELAYS

        if strict_mode:
            labels = {
                "uz": "🚨 Bu bugungi oxirgi eslatma. Hatto 15 daqiqa ham noldan yaxshi.",
                "ru": "🚨 Последнее напоминание на сегодня. Даже 15 минут лучше, чем ничего.",
                "en": "🚨 Final reminder for today. Even 15 minutes is better than zero.",
            }
            text = labels.get(lang, labels["en"])
        else:
            text = self.disc_engine.build_reminder_text(routine, lang)

        kb = quick_complete_kb(routine_id)

        try:
            await self.bot.send_message(uid, text, reply_markup=kb)
        except Exception as e:
            logger.warning("Failed delayed reminder to %d: %s", uid, e)

    async def handle_report(self, uid: int) -> str:
        from goal_system.report_service import build_daily_report
        lang = await self.db.get_language(uid)
        return await build_daily_report(self.db, uid, lang)

    async def _night_review_all(self):
        try:
            users = await self.db.fetchall(
                "SELECT DISTINCT user_id FROM routines WHERE active = 1"
            )
            for u in users:
                uid = u["user_id"]
                try:
                    lang = await self.db.get_language(uid)
                    report = await build_daily_report(self.db, uid, lang)
                    disc = await self.db.get_discipline(uid)
                    streak = disc["streak"]

                    labels = {
                        "uz": "🌙 *Kunlik Hisobot*",
                        "ru": "🌙 *Ежедневный Отчет*",
                        "en": "🌙 *Daily Review*",
                    }
                    header = labels.get(lang, labels["en"])

                    await self.bot.send_message(uid, f"{header}\n\n{report}")

                    if streak > 0:
                        streak_labels = {
                            "uz": f"\n\n🔥 {streak} kunlik streyk! Ajoyib davom eting!",
                            "ru": f"\n\n🔥 Серия {streak} дней! Продолжайте в том же духе!",
                            "en": f"\n\n🔥 {streak}-day streak! Keep it going!",
                        }
                        await self.bot.send_message(uid, streak_labels.get(lang, streak_labels["en"]))

                    if self.finance_engine:
                        try:
                            today_summary = await self.finance_engine.get_today_summary(uid, lang)
                            if today_summary:
                                fin_labels = {
                                    "uz": f"💰 *Kunlik moliya hisoboti*\n\n{today_summary}",
                                    "ru": f"💰 *Ежедневный финансовый отчет*\n\n{today_summary}",
                                    "en": f"💰 *Daily Finance Report*\n\n{today_summary}",
                                }
                                await self.bot.send_message(uid, fin_labels.get(lang, fin_labels["en"]))
                        except Exception as fe:
                            logger.warning("Finance night review failed for user %d: %s", uid, fe)
                except Exception as e:
                    logger.warning("Night review failed for user %d: %s", uid, e)
        except Exception as e:
            logger.exception("Night review cycle failed: %s", e)
