import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from .prompts import lang_rule

logger = logging.getLogger("ai_content_gen")

HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODEL = "NousResearch/Hermes-2-Pro-Llama-3-8B"
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


TASK_CONTENT_PROMPT = """{language_rule}

You are generating a short list of specific daily tasks for one goal only.

Goal: {goal_name}
User's data: {goal_answers}
User's profile: {profile}

Generate exactly 3-5 specific, actionable tasks the user can do TODAY for this goal.

Rules:
- Each task must be specific (include numbers: reps, sets, pages, minutes, problems, etc.)
- Use the user's actual answers to personalize
- Be challenging but achievable in one day
- NO headers, NO explanations, NO markdown
- Return ONLY a valid JSON array of strings

Example:
["Bench Press 4x8", "Shoulder Press 3x10", "Incline DB Press 3x10", "Tricep Pushdown 3x12"]"""


class AITaskContentGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_for_goal(self, goal_key: str, goal_name: str, goal_answers_text: str, profile_json: str, lang: str) -> list[str]:
        lang_rule_text = lang_rule(lang)
        prompt = TASK_CONTENT_PROMPT.format(
            language_rule=lang_rule_text,
            goal_name=goal_name,
            goal_answers=goal_answers_text or "No specific data provided.",
            profile=profile_json or "No profile data.",
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Generate today's tasks for {goal_name}"},
        ]

        for model in (MODEL, FALLBACK_MODEL):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1024,
                }
                resp = requests.post(
                    HF_BASE_URL,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(content[start:end])
                    if isinstance(parsed, list) and parsed:
                        return [str(t) for t in parsed if str(t).strip()]
            except Exception as e:
                logger.warning("Task content gen failed for %s with %s: %s", goal_name, model, e)

        return []

    async def generate_all(self, uid: int, goal_keys: list[str], goal_questions: dict, answers: dict, profile_json: str, lang: str) -> dict[str, list[str]]:
        from .goal_questions import GOAL_QUESTIONS, GOAL_DISPLAY_NAMES

        result = {}
        for key in goal_keys:
            goal_name = GOAL_DISPLAY_NAMES.get(key, key)
            goal_answers_text = ""
            questions = GOAL_QUESTIONS.get(key, [])
            for q in questions:
                field = q["field"]
                answer = answers.get(field, "no answer")
                goal_answers_text += f"{field}: {answer}\n"

            tasks = await self.generate_for_goal(key, goal_name, goal_answers_text, profile_json, lang)
            result[key] = tasks

        return result
