import random
from datetime import datetime, date
from typing import Optional

from modules.db import LifeDB
from modules.scheduler import SchedulerCoordinator
from modules.translations import LANGUAGES
from .messages import get_reminder_message

REMINDER_TYPES = ["water", "gym", "study", "work", "sleep", "supplement", "custom"]
REMINDER_LABELS = {
    "uz": {
        "water": "\U0001f4a7 Suv ichish",
        "gym": "\U0001f3cb\ufe0f Gym",
        "study": "\U0001f4da Dars",
        "work": "\U0001f4bc Ish",
        "sleep": "\U0001f634 Uyqu",
        "supplement": "\U0001f48a Vitamin",
        "custom": "\u270d\ufe0f Custom",
    },
    "ru": {
        "water": "\U0001f4a7 Пить воду",
        "gym": "\U0001f3cb\ufe0f Тренировка",
        "study": "\U0001f4da Учеба",
        "work": "\U0001f4bc Работа",
        "sleep": "\U0001f634 Сон",
        "supplement": "\U0001f48a Витамины",
        "custom": "\u270d\ufe0f Свой",
    },
    "en": {
        "water": "\U0001f4a7 Drink water",
        "gym": "\U0001f3cb\ufe0f Gym",
        "study": "\U0001f4da Study",
        "work": "\U0001f4bc Work",
        "sleep": "\U0001f634 Sleep",
        "supplement": "\U0001f48a Supplements",
        "custom": "\u270d\ufe0f Custom",
    },
}


def _lang(l: str) -> str:
    return l if l in LANGUAGES else "uz"


class ReminderEngine:
    def __init__(self, db: LifeDB, scheduler: SchedulerCoordinator, bot):
        self.db = db
        self.sched = scheduler
        self.bot = bot

    async def create_reminder(self, user_id: int, rtype: str, time: str, repeat: int = 1, custom_text: str = ""):
        rid = await self.db.add_reminder(user_id, rtype, time, repeat, custom_text)
        return rid

    async def delete_reminder(self, reminder_id: int):
        await self.db.delete_reminder(reminder_id)

    async def toggle_reminder(self, reminder_id: int, active: int):
        await self.db.toggle_reminder(reminder_id, active)

    async def get_user_reminders(self, user_id: int):
        return await self.db.get_reminders(user_id)

    async def get_reminder_list_text(self, user_id: int, lang: str = "uz") -> str:
        L = _lang(lang)
        reminders = await self.db.get_reminders(user_id)
        if not reminders:
            return "\U0001f4ad Hech qanday reminder yo'q." if L == "uz" else \
                   "\U0001f4ad Нет напоминаний." if L == "ru" else \
                   "\U0001f4ad No reminders."
        labels = REMINDER_LABELS[L]
        lines = ["\U0001f514 *Reminderlar*" if L == "uz" else "\U0001f514 *Напоминания*" if L == "ru" else "\U0001f514 *Reminders*"]
        for r in reminders:
            type_label = labels.get(r["type"], r["type"])
            repeat_str = "\U0001f501" if r["repeat"] else ""
            lines.append(f"  {r['id']}. {type_label} — {r['time']} {repeat_str}")
        return "\n".join(lines)

    async def send_reminder_notification(self, user_id: int, rtype: str, lang: str = "uz", custom_text: str = ""):
        L = _lang(lang)
        kwargs = {}
        if rtype == "water":
            kwargs["h"] = random.randint(2, 5)
        elif rtype == "custom" and custom_text:
            kwargs["text"] = custom_text
        msg = get_reminder_message(rtype, L, **kwargs)
        try:
            await self.bot.send_message(chat_id=user_id, text=msg)
        except Exception:
            pass

    async def schedule_all_active(self):
        reminders = await self.db.get_all_active_reminders()
        today = date.today().isoformat()
        for r in reminders:
            job_id = f"reminder_{r['id']}"
            time_str = r["time"]
            try:
                hour, minute = map(int, time_str.strip().split(":"))
                self.sched.add_cron(
                    job_id,
                    self._make_reminder_job(r["user_id"], r["type"], r["custom_text"]),
                    hour=hour,
                    minute=minute,
                )
            except (ValueError, TypeError):
                pass

    def _make_reminder_job(self, user_id: int, rtype: str, custom_text: str = ""):
        async def job_func():
            lang = "uz"
            try:
                from bot import db as main_db
                lang = await main_db.get_language(user_id)
            except Exception:
                pass
            await self.send_reminder_notification(user_id, rtype, lang, custom_text)
        return job_func
