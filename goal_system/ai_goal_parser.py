import json
import logging
from typing import Optional

from .prompts import AI_GOAL_PARSER_PROMPT, lang_rule
from .goal_questions import GOAL_DISPLAY_NAMES, GOAL_QUESTIONS, get_questions, get_category_for_goal

logger = logging.getLogger("goal_handlers")

HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODEL = "NousResearch/Hermes-2-Pro-Llama-3-8B"


def _query_hf(messages: list[dict], api_key: str) -> Optional[str]:
    import requests
    models = [MODEL, FALLBACK_MODEL]
    for model in models:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
            }
            resp = requests.post(
                HF_BASE_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content:
                return content
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            logger.warning("[AIGoalParser] Model %s HTTP %s: %s", model, status, e.response.text[:300])
            if status == 401:
                raise
        except Exception as e:
            logger.warning("[AIGoalParser] Model %s failed: %s", model, e)
    return None


class AIGoalParseResult:
    def __init__(
        self,
        mapped_goal_keys: list[str],
        category: str,
        normalized_goal: str,
        confidence: float,
        reasoning: str,
        raw_input: str,
    ):
        self.mapped_goal_keys = mapped_goal_keys
        self.category = category
        self.normalized_goal = normalized_goal
        self.confidence = confidence
        self.reasoning = reasoning
        self.raw_input = raw_input
        self.source = "ai"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "mapped_goal_keys": self.mapped_goal_keys,
            "category": self.category,
            "normalized_goal": self.normalized_goal,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "raw_input": self.raw_input,
        }


class AIGoalParser:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def parse(self, goal_text: str, lang: str = "uz") -> AIGoalParseResult:
        L = lang if lang in ("uz", "ru", "en") else "uz"
        lang_rule_text = lang_rule(L)
        prompt = AI_GOAL_PARSER_PROMPT.format(
            language_rule=lang_rule_text,
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": goal_text},
        ]

        try:
            content = _query_hf(messages, self.api_key)
            if content:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(content[start:end])
                    mapped_keys = data.get("mapped_goal_keys", [])
                    valid_keys = [k for k in mapped_keys if k in GOAL_DISPLAY_NAMES]
                    if valid_keys:
                        result = AIGoalParseResult(
                            mapped_goal_keys=valid_keys,
                            category=data.get("category", "general"),
                            normalized_goal=data.get("normalized_goal", goal_text),
                            confidence=data.get("confidence", 0.5),
                            reasoning=data.get("reasoning", "AI parsed"),
                            raw_input=goal_text,
                        )
                        logger.info(
                            "[AIGoalParser] Parsed goal: %s -> keys=%s category=%s confidence=%.2f reasoning=%s",
                            goal_text[:50], valid_keys, result.category, result.confidence, result.reasoning
                        )
                        return result
        except Exception as e:
            logger.warning("[AIGoalParser] Parse failed for %s: %s", goal_text[:50], e)

        return self._fallback(goal_text, L)

    def _fallback(self, goal_text: str, lang: str) -> AIGoalParseResult:
        goal_lower = goal_text.lower()
        keyword_map = {
            "sleep": "better_sleep",
            "uyqu": "better_sleep",
            "cortisol": ["better_sleep", "meditation", "healthy_eating"],
            "stress": ["meditation", "better_sleep", "discipline"],
            "anxiety": ["meditation", "better_sleep", "discipline"],
            "medit": "meditation",
            "german": "english",
            "french": "english",
            "spanish": "english",
            "ielts": "english",
            "toefl": "english",
            "english": "english",
            "frontend": "programming",
            "backend": "programming",
            "developer": "programming",
            "coding": "programming",
            "programming": "programming",
            "python": "programming",
            "javascript": "programming",
            "weight": ["gain_muscle", "lose_weight"],
            "muscle": "gain_muscle",
            "gym": "gain_muscle",
            "fat": "lose_weight",
            "diet": "healthy_eating",
            "eat": "healthy_eating",
            "food": "healthy_eating",
            "business": "business",
            "freelance": "freelancing",
            "money": ["freelancing", "business"],
            "focus": "focus",
            "discipline": "discipline",
            "productiv": "productivity",
            "reading": "reading",
            "book": "reading",
            "social": "social_skills",
            "confidence": ["social_skills", "discipline"],
            "mma": ["gain_muscle", "cardio", "discipline"],
            "looks": "looksmaxing",
            "skin": "looksmaxing",
            "groom": "looksmaxing",
        }

        mapped = set()
        for keyword, goal_key in keyword_map.items():
            if keyword in goal_lower:
                if isinstance(goal_key, list):
                    mapped.update(goal_key)
                else:
                    mapped.add(goal_key)

        if mapped:
            valid_keys = [k for k in mapped if k in GOAL_DISPLAY_NAMES]
            if valid_keys:
                category = get_category_for_goal(valid_keys[0])
                logger.info(
                    "[AIGoalParser] Fallback keyword match: %s -> keys=%s",
                    goal_text[:50], valid_keys
                )
                return AIGoalParseResult(
                    mapped_goal_keys=valid_keys,
                    category=category or "general",
                    normalized_goal=goal_text,
                    confidence=0.6,
                    reasoning=f"Keyword fallback match in: {goal_text[:50]}",
                    raw_input=goal_text,
                )

        health_related = {"workout", "exercise", "health", "fit", "body", "run", "cardio"}
        learning_related = {"learn", "study", "skill", "course", "class", "lesson", "teach", "read"}
        career_related = {"job", "career", "work", "salary", "promotion", "income", "earn"}
        mental_related = {"mind", "calm", "peace", "mental", "mood", "emotion", "habit"}

        def score(text: str, keywords: set) -> int:
            return sum(1 for kw in keywords if kw in text)

        scores = {
            "fitness": score(goal_lower, health_related),
            "learning": score(goal_lower, learning_related),
            "future_career": score(goal_lower, career_related),
            "mental_productivity": score(goal_lower, mental_related),
        }

        best_category = max(scores, key=scores.get)
        if scores[best_category] > 0:
            logger.info(
                "[AIGoalParser] Fallback category match: %s -> category=%s score=%d",
                goal_text[:50], best_category, scores[best_category]
            )

        return AIGoalParseResult(
            mapped_goal_keys=[],
            category="general",
            normalized_goal=goal_text,
            confidence=0.3,
            reasoning=f"Category heuristic: best_match={best_category} (score={scores[best_category]})",
            raw_input=goal_text,
        )
