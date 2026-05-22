from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo
from datetime import datetime
from typing import Callable, Optional

TZ = ZoneInfo("Asia/Tashkent")


class SchedulerCoordinator:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=TZ)
        self._jobs: dict[str, str] = {}

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def add_cron(self, job_id: str, func: Callable, **cron_kwargs):
        self.scheduler.add_job(func, CronTrigger(**cron_kwargs, timezone=TZ), id=job_id, replace_existing=True)
        self._jobs[job_id] = "cron"

    def add_interval(self, job_id: str, func: Callable, **interval_kwargs):
        self.scheduler.add_job(func, IntervalTrigger(**interval_kwargs, timezone=TZ), id=job_id, replace_existing=True)
        self._jobs[job_id] = "interval"

    def add_once(self, job_id: str, func: Callable, run_date: datetime):
        self.scheduler.add_job(func, DateTrigger(run_date=run_date), id=job_id, replace_existing=True)
        self._jobs[job_id] = "once"

    def remove_job(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
            self._jobs.pop(job_id, None)
        except Exception:
            pass

    def get_jobs(self):
        return self.scheduler.get_jobs()
