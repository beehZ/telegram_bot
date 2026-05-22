from datetime import date, datetime, timedelta
from typing import Optional

from modules.db import LifeDB
from modules.scheduler import SchedulerCoordinator
from modules.translations import LANGUAGES
from .messages import get_exam_message, get_study_message, get_homework_reminder, get_focus_message


def _lang(l: str) -> str:
    return l if l in LANGUAGES else "uz"


class StudentEngine:
    def __init__(self, db: LifeDB, scheduler: SchedulerCoordinator, bot):
        self.db = db
        self.sched = scheduler
        self.bot = bot

    # ── Exams ──

    async def add_exam(self, user_id: int, subject: str, exam_date: str):
        return await self.db.add_exam(user_id, subject, exam_date)

    async def get_exams(self, user_id: int):
        return await self.db.get_exams(user_id)

    async def delete_exam(self, exam_id: int):
        await self.db.delete_exam(exam_id)

    async def get_exams_text(self, user_id: int, lang: str = "uz") -> str:
        L = _lang(lang)
        exams = await self.db.get_exams(user_id)
        today = date.today()
        if not exams:
            if L == "uz":
                return "Hech qanday imtihon mavjud emas."
            elif L == "ru":
                return "Нет предстоящих экзаменов."
            return "No upcoming exams."

        lines = ["\U0001f4dd *Imtihonlar*" if L == "uz" else "\U0001f4dd *Экзамены*" if L == "ru" else "\U0001f4dd *Exams*"]
        for ex in exams:
            try:
                d = date.fromisoformat(ex["exam_date"])
                days = (d - today).days
                prefix = "\u26a0\ufe0f" if days <= 3 else "\U0001f4c5"
                lines.append(f"{prefix} {ex['subject']} — {ex['exam_date']} ({days} kun qoldi)" if L == "uz" else
                            f"{prefix} {ex['subject']} — {ex['exam_date']} (осталось {days} дн.)" if L == "ru" else
                            f"{prefix} {ex['subject']} — {ex['exam_date']} ({days} days left)")
            except (ValueError, TypeError):
                lines.append(f"\U0001f4c5 {ex['subject']} — {ex['exam_date']}")
        return "\n".join(lines)

    async def check_exam_reminders(self):
        exams = await self.db.get_upcoming_exams()
        today = date.today()
        for ex in exams:
            try:
                d = date.fromisoformat(ex["exam_date"])
                days = (d - today).days
                if 0 <= days <= 3:
                    user_id = ex["user_id"]
                    lang = "uz"
                    try:
                        from bot import db as main_db
                        lang = await main_db.get_language(user_id)
                    except Exception:
                        pass
                    msg = get_exam_message(user_id, ex["subject"], days, False, lang)
                    try:
                        await self.bot.send_message(chat_id=user_id, text=msg)
                    except Exception:
                        pass
                    await self.db.mark_exam_notified(ex["id"])
            except (ValueError, TypeError):
                pass

    # ── Study Log ──

    async def log_study(self, user_id: int, hours: float, lang: str = "uz") -> dict:
        L = _lang(lang)
        today = date.today().isoformat()
        await self.db.log_study(user_id, today, hours)

        streak_data = await self.db.get_study_streak(user_id)
        streak = streak_data.get("streak", 0)
        last_date = streak_data.get("last_date")

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last_date == yesterday:
            streak += 1
        elif last_date == today:
            pass
        else:
            streak = 1
        await self.db.update_study_streak(user_id, streak, today)

        msg = get_study_message(hours, L)
        streak_msg = ""
        for m in (3, 7, 14, 21, 30):
            if streak >= m:
                milestones = {
                    3: ("3 kunlik study streak!" if L == "uz" else "3-дневная серия учебы!" if L == "ru" else "3-day study streak!"),
                    7: ("7 kun! \U0001f525" if L == "uz" else "7 дней! \U0001f525" if L == "ru" else "7 days! \U0001f525"),
                    14: ("14 kun study streak \U0001f4aa" if L == "uz" else "14 дней учебы \U0001f4aa" if L == "ru" else "14-day study streak \U0001f4aa"),
                    21: ("21 kun. Habit locked \U0001f512" if L == "uz" else "21 день. Привычка закреплена \U0001f512" if L == "ru" else "21 days. Habit locked \U0001f512"),
                    30: ("30 kun! Study legend \U0001f3c6" if L == "uz" else "30 дней! Легенда учебы \U0001f3c6" if L == "ru" else "30 days! Study legend \U0001f3c6"),
                }
                streak_msg = milestones.get(m, "")
        if streak_msg:
            msg += f"\n\n{streak_msg}"

        return {"ok": True, "hours": hours, "streak": streak, "message": msg}

    async def get_today_study(self, user_id: int):
        today = date.today().isoformat()
        return await self.db.get_today_study(user_id, today)

    async def get_study_stats_text(self, user_id: int, lang: str = "uz") -> str:
        L = _lang(lang)
        today_hours = await self.get_today_study(user_id)
        streak_data = await self.db.get_study_streak(user_id)
        streak = streak_data.get("streak", 0)
        logs = await self.db.get_study_logs(user_id, 7)
        week_hours = sum(log["hours"] for log in logs)

        if L == "uz":
            return f"\U0001f4ca *Study Stats*\nBugun: {today_hours}h\nBu hafta: {week_hours}h\nStreak: {streak} kun"
        elif L == "ru":
            return f"\U0001f4ca *Статистика учебы*\nСегодня: {today_hours}ч\nНа этой неделе: {week_hours}ч\nСерия: {streak} дн."
        return f"\U0001f4ca *Study Stats*\nToday: {today_hours}h\nThis week: {week_hours}h\nStreak: {streak} days"

    # ── Homework ──

    async def add_homework(self, user_id: int, task: str):
        today = date.today().isoformat()
        return await self.db.add_homework(user_id, task, today)

    async def get_homework(self, user_id: int, date_str: Optional[str] = None):
        return await self.db.get_homework(user_id, date_str)

    async def complete_homework(self, homework_id: int):
        await self.db.complete_homework(homework_id)

    async def delete_homework(self, homework_id: int):
        await self.db.delete_homework(homework_id)

    async def get_homework_text(self, user_id: int, lang: str = "uz") -> str:
        L = _lang(lang)
        today = date.today().isoformat()
        homework = await self.db.get_homework(user_id, today)
        if not homework:
            if L == "uz":
                return "Bugun uchun hech qanday topshiriq yo'q."
            elif L == "ru":
                return "Нет заданий на сегодня."
            return "No homework for today."

        lines = ["\U0001f4cb *Homework*" if L == "uz" else "\U0001f4cb *Домашнее задание*" if L == "ru" else "\U0001f4cb *Homework*"]
        for hw in homework:
            status = "\u2705" if hw["completed"] else "\u274c"
            lines.append(f"  {hw['id']}. {status} {hw['task']}")
        return "\n".join(lines)

    # ── Focus / Pomodoro ──

    async def start_focus(self, user_id: int, lang: str = "uz") -> dict:
        L = _lang(lang)
        now = datetime.now().isoformat()
        session_id = await self.db.start_focus(user_id, now, 25)

        self.sched.add_once(
            f"focus_end_{session_id}",
            self._make_focus_complete(user_id, session_id, L),
            datetime.now() + timedelta(minutes=25),
        )

        msg = get_focus_message("start", L)
        return {"ok": True, "session_id": session_id, "message": msg}

    async def complete_focus(self, session_id: int, lang: str = "uz") -> str:
        L = _lang(lang)
        await self.db.complete_focus(session_id)
        self.sched.remove_job(f"focus_end_{session_id}")
        return get_focus_message("done", L)

    async def get_active_focus(self, user_id: int):
        return await self.db.get_active_focus(user_id)

    async def get_today_focus_count(self, user_id: int):
        today = date.today().isoformat()
        return await self.db.get_today_focus_count(user_id, today)

    async def schedule_exam_checks(self):
        self.sched.add_cron("exam_reminder_check", self.check_exam_reminders, hour=9, minute=0)

    def _make_focus_complete(self, user_id: int, session_id: int, lang: str):
        async def job():
            await self.db.complete_focus(session_id)
            msg = get_focus_message("done", lang)
            try:
                await self.bot.send_message(chat_id=user_id, text=msg)
            except Exception:
                pass
        return job
