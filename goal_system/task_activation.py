import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from goal_system.discipline_keyboards import (
    task_action_kb, active_task_kb, active_task_with_focus_kb,
    paused_task_kb, switch_task_kb,
    today_dashboard_kb, focus_options_kb,
)

logger = logging.getLogger("task_activation")

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


class ManualTaskTracker:
    def __init__(self, db, bot, discipline_engine):
        self.db = db
        self.bot = bot
        self.disc_engine = discipline_engine
        self._scheduler = None

    def set_scheduler(self, scheduler):
        self._scheduler = scheduler

    async def get_today_dashboard(self, uid: int, lang: str = "uz") -> tuple[str, object]:
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        routines = await self.db.get_todays_routines(uid)
        logs = await self.db.get_task_logs(uid, today)
        disc = await self.db.get_discipline(uid)
        active = await self.db.get_active_session(uid)

        log_map = {}
        for l in logs:
            log_map[l["routine_id"]] = l

        active_rid = active["routine_id"] if active else None

        completed_tasks = []
        active_task = None
        upcoming_tasks = []
        missed_tasks = []

        now_time = datetime.now(TASHKENT_TZ).strftime("%H:%M")

        for r in routines:
            l = log_map.get(r["id"])
            if l and l["status"] in ("completed", "partial"):
                completed_tasks.append(r)
            elif r["id"] == active_rid:
                active_task = r
            elif l and l["status"] == "skipped":
                missed_tasks.append(r)
            elif r["scheduled_time"] <= now_time and (l is None or l["status"] == "pending"):
                missed_tasks.append(r)
            else:
                upcoming_tasks.append(r)

        labels = {
            "uz": {
                "title": "📅 *Bugungi Vazifalar*",
                "completed": "✅ Bajarilgan",
                "active": "🔥 Aktiv",
                "upcoming": "📌 Keyingi",
                "missed": "❌ O'tkazib yuborilgan",
                "none": "Bugun uchun vazifalar yo'q",
                "xp": f"⭐ XP: {disc['xp']}",
                "streak": f"🔥 Streak: {disc['streak']} kun",
                "score": f"🎯 Intizom ball: {disc['discipline_score']}/100",
            },
            "ru": {
                "title": "📅 *Задачи на сегодня*",
                "completed": "✅ Выполнено",
                "active": "🔥 Активно",
                "upcoming": "📌 Предстоящие",
                "missed": "❌ Пропущено",
                "none": "На сегодня задач нет",
                "xp": f"⭐ XP: {disc['xp']}",
                "streak": f"🔥 Серия: {disc['streak']} дн.",
                "score": f"🎯 Балл: {disc['discipline_score']}/100",
            },
            "en": {
                "title": "📅 *Today's Tasks*",
                "completed": "✅ Completed",
                "active": "🔥 Active",
                "upcoming": "📌 Upcoming",
                "missed": "❌ Missed",
                "none": "No tasks scheduled for today",
                "xp": f"⭐ XP: {disc['xp']}",
                "streak": f"🔥 Streak: {disc['streak']} days",
                "score": f"🎯 Score: {disc['discipline_score']}/100",
            },
        }
        lbl = labels.get(lang, labels["en"])

        lines = [lbl["title"], ""]

        if active_task:
            lines.append(f"*{lbl['active']}*")
            lines.append(f"🕗 {active_task['scheduled_time']} — *{active_task['title']}*")
            lines.append("")

        if completed_tasks:
            lines.append(f"*{lbl['completed']}*")
            for r in completed_tasks:
                lines.append(f"✅ {r['scheduled_time']} — {r['title']}")
            lines.append("")

        for r in missed_tasks:
            if r["id"] != active_rid:
                lines.append(f"❌ {r['scheduled_time']} — {r['title']}")

        if upcoming_tasks:
            lines.append(f"*{lbl['upcoming']}*")
            for r in upcoming_tasks:
                if r["id"] != active_rid:
                    lines.append(f"📌 {r['scheduled_time']} — {r['title']}")

        if not routines:
            lines.append(lbl["none"])

        lines.append("")
        lines.append(lbl["streak"])
        lines.append(lbl["xp"])
        lines.append(lbl["score"])

        kb = today_dashboard_kb(routines, logs, active_rid)
        return "\n".join(lines), kb

    async def start_task(self, uid: int, routine_id: int, lang: str = "uz") -> tuple[str, object]:
        active = await self.db.get_active_session(uid)
        if active:
            existing_routine = await self.db.get_routine(active["routine_id"])
            existing_title = existing_routine["title"] if existing_routine else "?"
            new_routine = await self.db.get_routine(routine_id)
            new_title = new_routine["title"] if new_routine else "?"
            labels = {
                "uz": f"⚠️ Sizda aktiv vazifa bor:\n*{existing_title}*\n\nUni to'xtatib, *{new_title}* ni boshlashni xohlaysizmi?",
                "ru": f"⚠️ У вас уже есть активная задача:\n*{existing_title}*\n\nХотите остановить ее и начать *{new_title}*?",
                "en": f"⚠️ You already have an active task:\n*{existing_title}*\n\nDo you want to stop it and start *{new_title}*?",
            }
            kb = switch_task_kb(routine_id)
            return labels.get(lang, labels["en"]), kb

        routine = await self.db.get_routine(routine_id)
        if not routine:
            return "Task not found.", None

        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        existing_log = await self.db.fetchone(
            "SELECT id FROM task_logs WHERE user_id = ? AND routine_id = ? AND date = ? AND status IN ('completed','partial')",
            (uid, routine_id, today),
        )
        if existing_log:
            labels = {
                "uz": "✅ Bu vazifa bugun allaqachon bajarilgan!",
                "ru": "✅ Эта задача уже выполнена сегодня!",
                "en": "✅ This task is already completed today!",
            }
            return labels.get(lang, labels["en"]), None

        session_id = await self.db.create_active_session(uid, routine_id)
        await self.db.log_task(uid, routine_id, today, "in_progress")

        goal_focus = routine.get("description") or ""

        labels = {
            "uz": f"🔥 *{routine['title']}* sessiyasi boshlandi!\n\n⏰ Rejalashtirilgan: {routine['duration_minutes']} daqiqa\n🎯 Maqsad: {goal_focus}\n\nDiqqatni jamlang va muvaffaqiyatli yakunlang.",
            "ru": f"🔥 *{routine['title']}* сессия началась!\n\n⏰ Запланировано: {routine['duration_minutes']} мин\n🎯 Цель: {goal_focus}\n\nСосредоточьтесь и завершите успешно.",
            "en": f"🔥 *{routine['title']}* Session Started\n\n⏰ Planned Duration: {routine['duration_minutes']} minutes\n🎯 Focus Goal: {goal_focus}\n\nStay focused and finish strong.",
        }

        kb = active_task_kb(routine_id)
        return labels.get(lang, labels["en"]), kb

    async def finish_task(self, uid: int, routine_id: int, lang: str = "uz") -> str:
        session = await self.db.get_active_session(uid)
        routine = await self.db.get_routine(routine_id)
        if not routine:
            difficulty = "medium"
        else:
            difficulty = routine["difficulty"]

        await self.db.resume_active_session(uid)

        session = await self.db.get_active_session(uid)

        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")

        started_at_str = session["started_at"] if session else datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
        started_dt = datetime.strptime(started_at_str, "%Y-%m-%d %H:%M:%S") if " " in started_at_str else datetime.strptime(started_at_str, "%Y-%m-%d")
        now_dt = datetime.now()
        total_seconds = int((now_dt - started_dt).total_seconds())
        total_pause = session["total_pause_seconds"] if session else 0
        active_seconds = max(0, total_seconds - total_pause)
        actual_minutes = active_seconds // 60
        planned = routine["duration_minutes"] if routine else 30

        await self.db.delete_active_session(uid)

        xp_base = {"easy": 10, "medium": 25, "hard": 50}.get(difficulty, 25)
        disc = await self.db.get_discipline(uid)
        streak_bonus = 0
        if disc["streak"] >= 30:
            streak_bonus = int(xp_base * 0.5)
        elif disc["streak"] >= 7:
            streak_bonus = int(xp_base * 0.2)
        total_xp = xp_base + streak_bonus

        await self.db.award_xp(uid, total_xp)
        await self.db.log_task(uid, routine_id, today, "completed", total_xp)
        disc2 = await self.db.get_discipline(uid)
        await self.db.update_discipline(
            uid,
            total_completed=disc2["total_completed"] + 1,
        )
        await self.disc_engine.update_streak(uid)
        await self.disc_engine.update_discipline_score(uid)
        updated_disc = await self.db.get_discipline(uid)

        if actual_minutes < planned * 0.5:
            efficiency = "low"
        elif actual_minutes < planned * 0.8:
            efficiency = "medium"
        else:
            efficiency = "high"

        motivation_variants = {
            "uz": {
                "high": "Ajoyib natija! Bugun juda samarali bo'ldingiz.",
                "medium": "Yaxshi! Bajarildi — harakat davom etmoqda.",
                "low": "Boshlangan ish — yarim ish. Ertaga davom eting!",
            },
            "ru": {
                "high": "Отличный результат! Сегодня вы были очень продуктивны.",
                "medium": "Хорошо! Задача выполнена — прогресс продолжается.",
                "low": "Начато — наполовину сделано. Продолжайте завтра!",
            },
            "en": {
                "high": "Excellent result! You were very productive today.",
                "medium": "Good! Task completed — progress continues.",
                "low": "Well begun is half done. Continue tomorrow!",
            },
        }
        mot = motivation_variants.get(lang, motivation_variants["en"]).get(efficiency, motivation_variants["en"]["medium"])

        labels = {
            "uz": f"🔥 *Sessiya Yakunlandi!*\n\n⏱ Davomiylik: {actual_minutes} daqiqa\n⏰ Rejalashtirilgan: {planned} daqiqa\n⭐ XP: +{total_xp}\n📈 Streak: {updated_disc['streak']} kun\n🎯 Intizom ball: {updated_disc['discipline_score']}/100\n\n{mot}",
            "ru": f"🔥 *Сессия Завершена!*\n\n⏱ Длительность: {actual_minutes} мин\n⏰ Запланировано: {planned} мин\n⭐ XP: +{total_xp}\n📈 Серия: {updated_disc['streak']} дн.\n🎯 Балл: {updated_disc['discipline_score']}/100\n\n{mot}",
            "en": f"🔥 *Session Complete!*\n\n⏱ Duration: {actual_minutes} minutes\n⏰ Planned: {planned} minutes\n⭐ XP Earned: +{total_xp}\n📈 Streak: {updated_disc['streak']} days\n🎯 Discipline Score: {updated_disc['discipline_score']}/100\n\n{mot}",
        }
        return labels.get(lang, labels["en"])

    async def pause_task(self, uid: int, routine_id: int, lang: str = "uz") -> tuple[str, object]:
        await self.db.pause_active_session(uid)
        labels = {
            "uz": "⏸ Vazifa vaqtincha to'xtatildi.\n\nQayta boshlash uchun ▶️ Resume tugmasini bosing.",
            "ru": "⏸ Задача приостановлена.\n\nЧтобы продолжить, нажмите ▶️ Resume.",
            "en": "⏸ Task paused.\n\nPress ▶️ Resume to continue.",
        }
        kb = paused_task_kb(routine_id)
        return labels.get(lang, labels["en"]), kb

    async def resume_task(self, uid: int, routine_id: int, lang: str = "uz") -> tuple[str, object]:
        await self.db.resume_active_session(uid)
        routine = await self.db.get_routine(routine_id)
        title = routine["title"] if routine else "Task"
        labels = {
            "uz": f"▶️ *{title}* davom etmoqda.\n\nDiqqatni jamlang!",
            "ru": f"▶️ *{title}* продолжается.\n\nСосредоточьтесь!",
            "en": f"▶️ *{title}* resumed.\n\nStay focused!",
        }
        kb = active_task_kb(routine_id)
        return labels.get(lang, labels["en"]), kb

    async def cancel_task(self, uid: int, routine_id: int, reason: str = "", lang: str = "uz") -> str:
        session = await self.db.get_active_session(uid)
        routine = await self.db.get_routine(routine_id)

        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        await self.db.log_task(uid, routine_id, today, "skipped")
        await self.db.delete_active_session(uid)

        disc = await self.db.get_discipline(uid)
        new_skipped = disc["total_skipped"] + 1
        await self.db.update_discipline(uid, total_skipped=new_skipped)
        await self.disc_engine.update_discipline_score(uid)
        updated = await self.db.get_discipline(uid)

        labels = {
            "uz": f"❌ *Vazifa bekor qilindi.*\n\n📉 Intizom ball: {updated['discipline_score']}/100\n\nErtaga yangi kuch bilan boshlang!",
            "ru": f"❌ *Задача отменена.*\n\n📉 Балл дисциплины: {updated['discipline_score']}/100\n\nЗавтра начните с новыми силами!",
            "en": f"❌ *Task cancelled.*\n\n📉 Discipline score: {updated['discipline_score']}/100\n\nStart fresh tomorrow!",
        }
        return labels.get(lang, labels["en"])

    async def switch_task(self, uid: int, old_routine_id: int, new_routine_id: int, lang: str = "uz") -> tuple[str, object]:
        await self.db.delete_active_session(uid)
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        await self.db.log_task(uid, old_routine_id, today, "skipped")
        return await self.start_task(uid, new_routine_id, lang)

    async def start_focus_mode(self, uid: int, routine_id: int, minutes: int = 25, lang: str = "uz") -> str:
        session = await self.db.get_active_session(uid)
        session_id = session["id"] if session else 0

        fid = await self.db.create_focus_session(uid, routine_id, session_id, minutes)
        await self.db.update_active_session(uid, focus_mode=1, focus_minutes=minutes)

        labels = {
            "uz": f"🎯 *{minutes} daqiqalik fokus sessiyasi boshlandi.*\n\nChalg'itadigan narsalardan uzoqroq turing. Diqqatni jamlang!",
            "ru": f"🎯 *{minutes}-минутная фокус-сессия началась.*\n\nДержитесь подальше от отвлекающих факторов. Сосредоточьтесь!",
            "en": f"🎯 *{minutes}-minute focus session started.*\n\nStay away from distractions. Stay focused!",
        }

        self._schedule_focus_complete(uid, routine_id, fid, minutes)
        return labels.get(lang, labels["en"])

    def _schedule_focus_complete(self, uid: int, routine_id: int, fid: int, minutes: int):
        if not self._scheduler:
            return
        from apscheduler.triggers.date import DateTrigger
        self._scheduler.add_job(
            self._focus_completed,
            DateTrigger(run_date=datetime.now(TASHKENT_TZ) + timedelta(minutes=minutes)),
            args=[uid, routine_id, fid],
            id=f"focus_{uid}_{routine_id}",
            replace_existing=True,
        )

    async def _focus_completed(self, uid: int, routine_id: int, fid: int):
        await self.db.complete_focus_session(fid)
        labels = {
            "uz": "🎉 *Fokus sessiyasi yakunlandi!* Ajoyib diqqat!",
            "ru": "🎉 *Фокус-сессия завершена!* Отличная концентрация!",
            "en": "🎉 *Focus session complete!* Great concentration!",
        }
        lang = await self.db.get_language(uid)
        try:
            await self.bot.send_message(uid, labels.get(lang, labels["en"]))
        except Exception as e:
            logger.warning("Focus complete message failed: %s", e)

    async def check_completed_before_reminder(self, uid: int, routine_id: int, date: str) -> bool:
        existing = await self.db.fetchone(
            "SELECT id FROM task_logs WHERE user_id = ? AND routine_id = ? AND date = ? AND status IN ('completed', 'partial')",
            (uid, routine_id, date),
        )
        if existing:
            return True
        active = await self.db.get_active_session(uid)
        if active and active["routine_id"] == routine_id:
            return True
        return False
