from datetime import date, datetime, timedelta
from typing import Optional

from modules.db import LifeDB
from modules.scheduler import SchedulerCoordinator
from modules.translations import LANGUAGES
from .messages import get_mood_response, get_streak_message

MOOD_EMOJI = {"good": "\U0001f60e", "mid": "\U0001f610", "bad": "\U0001f62d"}
MOOD_LABELS = {
    "uz": {"good": "Zo'r", "mid": "O'rtacha", "bad": "Yomon"},
    "ru": {"good": "Отлично", "mid": "Нормально", "bad": "Плохо"},
    "en": {"good": "Great", "mid": "Okay", "bad": "Bad"},
}


def _lang(l: str) -> str:
    return l if l in LANGUAGES else "uz"


class CheckinEngine:
    def __init__(self, db: LifeDB, scheduler: SchedulerCoordinator, bot):
        self.db = db
        self.sched = scheduler
        self.bot = bot

    async def process_checkin(self, user_id: int, mood: str, lang: str = "uz") -> dict:
        L = _lang(lang)
        today = date.today().isoformat()

        existing = await self.db.get_today_checkin(user_id, today)
        if existing:
            return {"ok": False, "message": self._already_checked_in_msg(L)}

        await self.db.add_checkin(user_id, today, mood)

        streak_data = await self.db.get_checkin_streak(user_id)
        current_streak = streak_data.get("streak", 0)
        last_date = streak_data.get("last_date")

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last_date == yesterday:
            current_streak += 1
        elif last_date == today:
            pass
        else:
            current_streak = 1

        await self.db.update_checkin_streak(user_id, current_streak, today)

        mood_msg = get_mood_response(mood, L)
        streak_msg = get_streak_message(current_streak, L)

        lines = [mood_msg]
        if streak_msg:
            lines.append("")
            lines.append(streak_msg)

        lines.append("")
        recent = await self.db.get_checkins(user_id, 7)
        mood_counts = {"good": 0, "mid": 0, "bad": 0}
        for c in recent:
            m = c["mood"]
            if m in mood_counts:
                mood_counts[m] += 1
        total = sum(mood_counts.values())
        if total > 0:
            mini_report = self._mood_mini_report(mood_counts, total, L)
            lines.append(mini_report)

        return {
            "ok": True,
            "mood": mood,
            "streak": current_streak,
            "message": "\n".join(lines),
        }

    async def get_checkin_status(self, user_id: int, lang: str = "uz") -> dict:
        L = _lang(lang)
        today = date.today().isoformat()
        existing = await self.db.get_today_checkin(user_id, today)
        streak_data = await self.db.get_checkin_streak(user_id)
        streak = streak_data.get("streak", 0)
        return {
            "done_today": existing is not None,
            "streak": streak,
            "message": self._status_text(existing is not None, streak, L),
        }

    async def schedule_daily_checkin(self, hour: int = 20, minute: int = 0):
        self.sched.add_cron(
            "daily_checkin_prompt",
            self._send_checkin_prompts,
            hour=hour,
            minute=minute,
        )

    async def _send_checkin_prompts(self):
        pass

    def _already_checked_in_msg(self, lang: str) -> str:
        if lang == "uz":
            return "Bugun ro'yxatdan o'tgansiz \U0001f44c Ertaga yana ko'rishamiz!"
        elif lang == "ru":
            return "Вы уже отметились сегодня \U0001f44c Увидимся завтра!"
        return "You've already checked in today \U0001f44c See you tomorrow!"

    def _status_text(self, done: bool, streak: int, lang: str) -> str:
        if done:
            if lang == "uz":
                return f"Bugun check-in qilindingiz \u2705 Streak: {streak} kun \U0001f525"
            elif lang == "ru":
                return f"Вы отметились сегодня \u2705 Серия: {streak} дней \U0001f525"
            return f"Checked in today \u2705 Streak: {streak} days \U0001f525"
        else:
            if lang == "uz":
                return "Bugun hali check-in qilmagansiz \U0001f514"
            elif lang == "ru":
                return "Вы еще не отметились сегодня \U0001f514"
            return "Haven't checked in today yet \U0001f514"

    def _mood_mini_report(self, counts: dict, total: int, lang: str) -> str:
        good_pct = round(counts["good"] / total * 100)
        labels = MOOD_LABELS.get(lang, MOOD_LABELS["uz"])
        if lang == "uz":
            return f"7 kunlik kayfiyat: {labels['good']} {counts['good']}x, {labels['mid']} {counts['mid']}x, {labels['bad']} {counts['bad']}x"
        elif lang == "ru":
            return f"Настроение за 7 дней: {labels['good']} {counts['good']}x, {labels['mid']} {counts['mid']}x, {labels['bad']} {counts['bad']}x"
        return f"7-day mood: {labels['good']} {counts['good']}x, {labels['mid']} {counts['mid']}x, {labels['bad']} {counts['bad']}x"
