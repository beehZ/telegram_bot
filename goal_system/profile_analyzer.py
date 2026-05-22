import json
import logging

import requests

from .prompts import lang_rule, PROFILE_ANALYSIS_PROMPT

logger = logging.getLogger("profile_analyzer")

HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODEL = "NousResearch/Hermes-2-Pro-Llama-3-8B"


class ProfileAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def analyze(self, goals_display: str, all_answers_text: str, lang: str = "uz"):
        lang_rule_text = lang_rule(lang)

        prompt = PROFILE_ANALYSIS_PROMPT.format(
            language_rule=lang_rule_text,
            goals=goals_display,
            all_answers=all_answers_text,
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Analyze my profile based on my answers above."},
        ]

        for model in (MODEL, FALLBACK_MODEL):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.3,
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
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                logger.warning("Profile analysis model %s HTTP %s: %s", model, status, e.response.text[:300])
                if status == 401:
                    raise
            except Exception as e:
                logger.warning("Profile analysis with %s failed: %s", model, e)

        return self._default_profile()

    def _default_profile(self):
        return {
            "discipline_level": 50,
            "fitness_level": "beginner",
            "learning_style": "mixed",
            "stress_level": 50,
            "sleep_quality": "fair",
            "focus_ability": 50,
            "productivity_level": 50,
            "motivation_type": "mixed",
            "consistency_score": 50,
            "confidence_level": 50,
            "main_weaknesses": ["consistency", "focus"],
            "main_strengths": ["motivation", "ambition"],
            "recommended_coach_approach": "balanced",
            "personality_summary": "Motivated learner looking to build discipline and achieve multiple goals.",
        }
