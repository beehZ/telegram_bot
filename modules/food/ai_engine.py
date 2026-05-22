import json
import logging
import re
from typing import Optional

import requests

from modules.food.engine import AggregatedNutrition
from modules.food.prompts import FOOD_ANALYSIS_PROMPT

logger = logging.getLogger("food.ai_engine")

HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODEL = "NousResearch/Hermes-2-Pro-Llama-3-8B"

FOOD_EMOJI_MAP = {
    "coffee": "☕", "kofe": "☕", "tea": "🍵", "choy": "🍵",
    "tuxum": "🥚", "egg": "🥚", "non": "🍞", "bread": "🍞",
    "sut": "🥛", "milk": "🥛", "banan": "🍌", "banana": "🍌",
    "olma": "🍎", "apple": "🍎", "nok": "🍐", "pear": "🍐",
    "apelsin": "🍊", "orange": "🍊", "uzum": "🍇", "grape": "🍇",
    "tarvuz": "🍉", "watermelon": "🍉", "qovun": "🍈",
    "shaftoli": "🍑", "peach": "🍑", "gilos": "🍒",
    "osh": "🍚", "palov": "🍚", "plov": "🍚",
    "shurva": "🍜", "soup": "🍜", "mastava": "🍜",
    "manti": "🥟", "somsa": "🥟", "lagman": "🍜",
    "kebab": "🥩", "shashlik": "🥩",
    "go'sht": "🥩", "tovuq": "🍗", "chicken": "🍗",
    "baliq": "🐟", "fish": "🐟", "burger": "🍔",
    "pizza": "🍕", "hot-dog": "🌭",
    "shokolad": "🍫", "chocolate": "🍫",
    "cake": "🎂", "tort": "🎂", "cookie": "🍪",
    "water": "💧", "suv": "💧",
    "salat": "🥗", "sabzi": "🥕", "carrot": "🥕",
    "pomidor": "🍅", "tomato": "🍅", "bodring": "🥒",
    "kartoshka": "🥔", "potato": "🥔",
    "pishloq": "🧀", "cheese": "🧀",
    "sariyog'": "🧈", "butter": "🧈",
}


def query_ai(messages: list[dict], api_key: str) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    models_to_try = [MODEL, FALLBACK_MODEL]
    for model in models_to_try:
        try:
            payload["model"] = model
            resp = requests.post(HF_BASE_URL, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            logger.warning("AI model %s HTTP %s: %s", model, e.response.status_code, e.response.text[:200])
            if e.response.status_code == 401:
                raise
        except requests.exceptions.Timeout:
            logger.warning("AI model %s timed out", model)
        except Exception as e:
            logger.exception("AI model %s error: %s", model, e)
    return None


def extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            start = text.index('{')
            end = text.rindex('}') + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return None


def get_emoji(food_name: str) -> str:
    fn = food_name.lower()
    for key, emoji in FOOD_EMOJI_MAP.items():
        if key in fn:
            return emoji
    return "🍽️"


def format_result(data: dict, remain: int, lang: str = "uz") -> str:
    labels = {
        "uz": {
            "remain": f"📊 Bugungi normangizdan yana {remain} kcal qoldi",
            "next": "Yana ovqat yozing yoki /summary bilan kunlik hisobni ko'ring!",
            "vitamins": "💊 Vitaminlar va Minerallar:",
            "total": "JAMI",
        },
        "ru": {
            "remain": f"📊 Осталось {remain} ккал от вашей дневной нормы",
            "next": "Запишите ещё еду или проверьте /summary",
            "vitamins": "💊 Витамины и Минералы:",
            "total": "ИТОГО",
        },
        "en": {
            "remain": f"📊 You have {remain} kcal remaining today",
            "next": "Log more food or check /summary for today's total",
            "vitamins": "💊 Vitamins & Minerals:",
            "total": "TOTAL",
        },
    }
    lbl = labels.get(lang, labels["uz"])
    items = data.get("items", [])
    lines = []

    for item in items:
        food_name = item.get("food", "?")
        emoji = get_emoji(food_name)
        amount = item.get("amount", 1)
        unit = item.get("unit", "piece")
        amt_str = f"{amount:g}" if isinstance(amount, float) and amount != int(amount) else str(int(amount))

        if unit in ("piece", "dona") and amount > 1:
            lines.append(f"{emoji} {int(amount)}ta {food_name.title()}")
        elif unit == "ml":
            lines.append(f"{emoji} {food_name.title()} ({amt_str}ml)")
        elif unit == "g":
            lines.append(f"{emoji} {food_name.title()} ({amt_str}g)")
        elif unit == "cup":
            lines.append(f"{emoji} {food_name.title()} ({amt_str} stakan)")
        else:
            lines.append(f"{emoji} {food_name.title()}")

        lines.append(f"🔥 Calories: {item.get('calories', 0)} kcal")
        lines.append(f"🥩 Protein: {item.get('protein', 0)} g")
        lines.append(f"🥑 Fat: {item.get('fat', 0)} g")
        lines.append(f"🍞 Carbs: {item.get('carbs', 0)} g")
        lines.append(f"🍬 Sugar: {item.get('sugar', 0)} g")
        lines.append(f"🌾 Fiber: {item.get('fiber', 0)} g")
        lines.append("")

    if len(items) > 1:
        total = data.get("total", {})
        lines.append(f"*{lbl['total']}:*")
        lines.append(
            f"🔥 {total.get('calories', 0)} kcal"
            f" | 🥩 {total.get('protein', 0)}g"
            f" | 🥑 {total.get('fat', 0)}g"
            f" | 🍞 {total.get('carbs', 0)}g"
        )
        lines.append("")

    vitamins = data.get("vitamins", [])
    if vitamins:
        lines.append(lbl["vitamins"])
        for v in vitamins:
            lines.append(f"• {v}")
        lines.append("")

    lines.append(lbl["remain"])
    lines.append("")
    lines.append(lbl["next"])
    return "\n".join(lines)


class AINutritionEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def analyze(self, text: str, context: Optional[str] = None) -> dict:
        system_msg = {"role": "system", "content": FOOD_ANALYSIS_PROMPT}
        user_content = text
        if context:
            user_content = f"Previous context: {context}\n\nUser added: {text}"
        messages = [system_msg, {"role": "user", "content": user_content}]
        reply = query_ai(messages, self.api_key)
        if not reply:
            return {"error": "AI response failed", "clarification_needed": False}

        data = extract_json(reply)
        if not data:
            return {
                "clarification_needed": False,
                "error": "Failed to parse AI response",
                "raw": reply,
            }

        data["_raw_reply"] = reply
        return data

    def analyze_with_history(self, messages: list[dict]) -> dict:
        reply = query_ai(messages, self.api_key)
        if not reply:
            return {"error": "AI response failed", "clarification_needed": False}
        data = extract_json(reply)
        if not data:
            return {
                "clarification_needed": False,
                "error": "Failed to parse AI response",
                "raw": reply,
            }
        data["_raw_reply"] = reply
        return data
