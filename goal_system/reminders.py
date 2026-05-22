import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("goal_reminders")

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


class ReminderManager:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)

    def start(self):
        self.scheduler.start()
        logger.info("Reminder scheduler started")

    async def load_reminders(self):
        jobs = self.scheduler.get_jobs()
        for j in jobs:
            j.remove()

        all_reminders = await self.db.fetchall(
            "SELECT r.*, u.user_id FROM reminders r JOIN users u ON u.user_id = r.user_id WHERE r.active = 1"
        )
        for rem in all_reminders:
            self._schedule_one(rem)

        logger.info("Loaded %d reminders", len(all_reminders))

    def _schedule_one(self, rem: dict):
        uid = rem["user_id"]
        rid = rem["id"]
        msg = rem["message"]
        time_str = rem["remind_time"]
        dow = rem.get("day_of_week", -1)

        try:
            hour, minute = map(int, time_str.split(":"))
        except (ValueError, AttributeError):
            logger.warning("Invalid time for reminder %d: %s", rid, time_str)
            return

        if dow == -1:
            trigger = CronTrigger(hour=hour, minute=minute, timezone=TASHKENT_TZ)
        else:
            trigger = CronTrigger(day_of_week=dow, hour=hour, minute=minute, timezone=TASHKENT_TZ)

        job = self.scheduler.add_job(
            self._send_reminder,
            trigger,
            args=[uid, msg, rid],
            id=f"reminder_{rid}",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Scheduled reminder %d: %s at %s (dow=%s)", rid, msg, time_str, dow)

    async def _send_reminder(self, uid: int, message: str, rid: int):
        try:
            await self.bot.send_message(uid, f"⏰ *Reminder:* {message}")
        except Exception as e:
            logger.warning("Failed to send reminder %d to %d: %s", rid, uid, e)

    async def create_reminders_for_schedule(self, uid: int, schedule_data: dict):
        reminders = schedule_data.get("reminders", [])
        for rem in reminders:
            time_str = rem.get("time", "08:00")
            msg = rem.get("message", "")
            goal_name = rem.get("goal", "general")
            goals = await self.db.get_goals(uid)
            goal_id = None
            for g in goals:
                if g["name"].lower() == goal_name.lower():
                    goal_id = g["id"]
                    break
            if not goal_id and goals:
                goal_id = goals[0]["id"]

            await self.db.save_reminder(uid, goal_id or 0, msg, time_str, -1)

        await self.load_reminders()

    async def stop(self):
        self.scheduler.shutdown(wait=False)
