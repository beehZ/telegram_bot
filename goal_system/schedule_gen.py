import logging
from typing import Optional

from .routine_engine import RoutineEngine

logger = logging.getLogger("goal_schedule")


class ScheduleGenerator:
    def __init__(self, api_key: str = "", prompts_module=None):
        self.api_key = api_key
        self.prompts = prompts_module
        self._engine = RoutineEngine()

    def generate(self, profile: dict = None, goals: list[dict] = None, goal_answers: dict = None, details: list[dict] = None, nutrition: dict = None, lang: str = "uz") -> dict | None:
        goal_keys = [g["name"] for g in (goals or [])]
        logger.info("ScheduleGenerator.generate called with goals: %s (using rule-based engine)", goal_keys)
        return None

    async def generate_async(self, selected_goal_keys: list[str]) -> list[dict]:
        return self._engine.generate(selected_goal_keys)
