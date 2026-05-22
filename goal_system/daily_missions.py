import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .prompts import lang_rule, DAILY_MISSIONS_PROMPT

logger = logging.getLogger("daily_missions")

HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODEL = "NousResearch/Hermes-2-Pro-Llama-3-8B"
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


class DailyMissionGenerator:
    def __init__(self, api_key: str, db):
        self.api_key = api_key
        self.db = db

    async def generate_missions(self, uid: int, goals_display: str, profile_json: str, lang: str = "uz", goal_answers: str = ""):
        lang_rule_text = lang_rule(lang)
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")

        # Check if already generated for today
        existing = await self.db.get_daily_missions(uid, today)
        if existing:
            missions = json.loads(existing["missions_json"])
            if missions:
                return missions

        prompt = DAILY_MISSIONS_PROMPT.format(
            language_rule=lang_rule_text,
            goals=goals_display,
            profile=profile_json,
            date=today,
            goal_answers=goal_answers or "No answers provided.",
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Generate today's missions for my goals: {goals_display}"},
        ]

        missions = None
        for model in (MODEL, FALLBACK_MODEL):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": 2048,
                }
                resp = requests.post(
                    HF_BASE_URL,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=180,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(content[start:end])
                    if isinstance(parsed, list):
                        missions = parsed
                        break
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                logger.warning("Missions gen model %s HTTP %s: %s", model, status, e.response.text[:300])
                if status == 401:
                    raise
            except Exception as e:
                logger.warning("Missions gen with %s failed: %s", model, e)

        if not missions:
            missions = self._default_missions(goals_display)

        await self.db.save_daily_missions(uid, json.dumps(missions, ensure_ascii=False), today)
        return missions

    def _default_missions(self, goals_display: str):
        return [
            {"mission": f"Work on {goals_display} for at least 1 hour", "goal": "general", "category": "general"},
            {"mission": "Drink 8 glasses of water", "goal": "general", "category": "fitness"},
            {"mission": "Do 20 minutes of physical activity", "goal": "general", "category": "fitness"},
            {"mission": "No phone 1 hour before bed", "goal": "general", "category": "mental"},
        ]

    async def get_todays_missions_data(self, uid: int):
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        row = await self.db.get_daily_missions(uid, today)
        if not row:
            return None
        missions = json.loads(row["missions_json"])
        if not missions:
            return None
        streak = await self.db.get_mission_streak(uid)
        completed = sum(1 for m in missions if m.get("completed"))
        total = len(missions)
        return missions, streak, completed, total

    @staticmethod
    def build_missions_text(missions: list, streak: int, completed: int, total: int, lang: str) -> str:
        headers = {
            "uz": f"🔥 *KUNLIK MISSIYALAR*\n\n✅ Bajarildi: {completed}/{total}  |  🔥 Streak: {streak} kun",
            "ru": f"🔥 *ЕЖЕДНЕВНЫЕ МИССИИ*\n\n✅ Выполнено: {completed}/{total}  |  🔥 Серия: {streak} дн.",
            "en": f"🔥 *DAILY MISSIONS*\n\n✅ Completed: {completed}/{total}  |  🔥 Streak: {streak} days",
        }
        lines = [headers.get(lang, headers["en"]), ""]
        emoji_map = {"fitness": "🏋️", "learning": "📚", "mental": "🧠", "career": "💼", "appearance": "🔥"}
        for m in missions:
            status = "✅" if m.get("completed") else "⬜"
            cat_emoji = emoji_map.get(m.get("category", "general"), "🎯")
            lines.append(f"{status} {cat_emoji} {m.get('mission', '?')}")
        return "\n".join(lines)

    @staticmethod
    def build_missions_keyboard(missions: list) -> InlineKeyboardMarkup:
        kb = []
        for i, m in enumerate(missions):
            if m.get("completed"):
                btn = InlineKeyboardButton(text="✔ Completed", callback_data=f"mc:{i}")
            else:
                btn = InlineKeyboardButton(text="✅ Complete", callback_data=f"mc:{i}")
            kb.append([btn])
        return InlineKeyboardMarkup(inline_keyboard=kb)

    async def get_todays_missions(self, uid: int, lang: str = "uz") -> str:
        data = await self.get_todays_missions_data(uid)
        if not data:
            labels = {
                "uz": "Bugun uchun missiyalar hali yaratilmagan. /goal orqali maqsadlaringizni belgilang!",
                "ru": "Миссии на сегодня еще не созданы. Установите цели через /goal!",
                "en": "No missions for today yet. Set your goals with /goal!",
            }
            return labels.get(lang, labels["en"])
        missions, streak, completed, total = data
        return self.build_missions_text(missions, streak, completed, total, lang)

    async def mark_complete(self, uid: int, mission_index: int, lang: str = "uz"):
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        row = await self.db.get_daily_missions(uid, today)
        if row:
            missions = json.loads(row["missions_json"])
            if 1 <= mission_index <= len(missions):
                await self.db.complete_mission(uid, today, mission_index - 1)
                labels = {
                    "uz": f"✅ {mission_index}-missiya bajarildi deb belgilandi!",
                    "ru": f"✅ Миссия {mission_index} отмечена как выполненная!",
                    "en": f"✅ Mission {mission_index} marked as complete!",
                }
                return labels.get(lang, labels["en"])
        labels = {
            "uz": f"❌ {mission_index}-missiya topilmadi. /missions orqali ro'yxatni ko'ring.",
            "ru": f"❌ Миссия {mission_index} не найдена. Проверьте список через /missions.",
            "en": f"❌ Mission {mission_index} not found. Check the list via /missions.",
        }
        return labels.get(lang, labels["en"])
