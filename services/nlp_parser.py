import json
import logging
import re

import requests

logger = logging.getLogger("nlp_parser")

HF_API_KEY = None
HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"

AMOUNT_PATTERNS = [
    (r'(\d{1,3}(?:\.\d{3})+)\s*(?:so\'m|som|сум)', 1, True),
    (r'(\d+(?:[.,]\d+)?)\s*(mln|million|млн)', 1_000_000, False),
    (r'(\d+(?:[.,]\d+)?)\s*(ming|минг)\s*(?:so\'m|som|сум)?', 1_000, False),
    (r'(\d+(?:[.,]\d+)?)\s*k\b', 1_000, False),
    (r'(\d+(?:[.,]\d+)?)\s*(?:so\'m|som|сум)', 1, False),
    (r'\b(\d{4,})\b', 1, False),
]

ITEM_PATTERN = r'(\d+)\s*(?:ta|dona|шт|штук)\s+(\w+)'

INCOME_WORDS = [
    "tushdi", "foyda", "daromad", "oylik", "maosh",
    "ish haqi", "qaytardi", "qaytdi", "yutdim", "topdim",
    "salary", "income", "received", "got",
]

EXPENSE_WORDS = [
    "ketdi", "berdim", "sarfladim", "xarajat", "to'ladim", "toladim",
    "oldim", "sotib", "ishlatdim", "chiqdim", "to'lov", "tolov",
    "gas", "taxi", "uchun", "bought", "spent", "berib yubordim",
]

INCOME_CATEGORY_KW = {
    "salary": ["oylik", "maosh", "ish haqi", "ishhaki", "oklad", "salary", "zam"],
    "business": ["biznes", "savdo", "tijorat", "mijoz", "foyda", "business", "zakaz"],
    "gift": ["sovg'a", "sovga", "hadya", "gift"],
    "freelance": ["freelance", "frilans", "upwork", "fiverr", "remote"],
    "debt_return": ["qarz", "qaytardi", "qaytdi", "debt", "qarzdor", "berdi"],
}

EXPENSE_CATEGORY_KW = {
    "food": ["ovqat", "taom", "non", "tuxum", "osh", "kafe", "restoran", "yegulik",
             "oziq", "food", "go'sht", "gosht", "nonushta", "tushlik", "kechki"],
    "transport": ["benzin", "taxi", "transport", "yo'l", "yol", "mashina", "gaz",
                  "bus", "metro", "avtobus", "poezd"],
    "shopping": ["kiyim", "poyabzal", "do'kon", "dokon", "magazin", "bozor",
                 "narsa", "buyum", "shopping"],
    "health": ["dori", "shifokor", "vrach", "kasal", "doctor", "dorixona",
               "bolnitsa", "tabletka", "kasalxona"],
    "education": ["o'qish", "oqish", "kurs", "dars", "maktab", "kitob",
                  "education", "univer", "o'quv", "oquv", "talim", "ta'lim"],
    "rent": ["ijara", "kvartira", "kommunal", "elektr", "uy", "shar", "arenda"],
    "gaming": ["o'yin", "oyin", "game", "pubg", "cs", "valoran"],
    "family": ["oila", "bola", "farzand"],
    "phone": ["telefon", "internet", "gsm", "uzmobile", "beeline", "ucell",
              "mobiuz", "tarif", "sim"],
}


def init_parser(api_key: str):
    global HF_API_KEY
    HF_API_KEY = api_key


def parse_money_text(text: str) -> dict:
    if not text or not text.strip():
        return {"amount": 0, "currency": "UZS", "tx_type": "expense",
                "category": "other", "items": [], "description": "", "raw_text": text}

    if HF_API_KEY:
        try:
            result = _parse_with_hf(text)
            if result and result.get("amount") and float(result["amount"]) > 0:
                result["raw_text"] = text
                return result
        except Exception as e:
            logger.warning("HF parse failed for '%s': %s", text[:60], e)

    result = _parse_with_regex(text)
    result["raw_text"] = text
    return result


def _parse_with_hf(text: str) -> dict:
    prompt = (
        "Extract financial transaction info. Return ONLY valid JSON.\n\n"
        f'Text: "{text}"\n\n'
        'Required JSON format:\n'
        '{\n'
        '  "amount": <number>,\n'
        '  "currency": "UZS" or "USD",\n'
        '  "tx_type": "expense" or "income",\n'
        '  "category": "food"|"transport"|"shopping"|"health"|"education"|"rent"|"gaming"|"family"|"phone"|"salary"|"business"|"gift"|"freelance"|"debt_return"|"other",\n'
        '  "items": [{"name": "<item_name>", "quantity": <number>}],\n'
        '  "description": "<short_description>"\n'
        '}\n\n'
        'Examples:\n'
        '"5ta tuxum 15000 som" -> {"amount":15000,"currency":"UZS","tx_type":"expense","category":"food","items":[{"name":"tuxum","quantity":5}],"description":"tuxum"}\n'
        '"1.500.000 som" -> {"amount":1500000,"currency":"UZS","tx_type":"expense","category":"other","items":[],"description":""}\n'
        '"200k" -> {"amount":200000,"currency":"UZS","tx_type":"expense","category":"other","items":[],"description":""}\n'
        '"maosh 5000000 som" -> {"amount":5000000,"currency":"UZS","tx_type":"income","category":"salary","items":[],"description":"maosh"}\n'
        '"gas uchun 20000" -> {"amount":20000,"currency":"UZS","tx_type":"expense","category":"transport","items":[],"description":"gas"}\n\n'
        "JSON:"
    )

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 256,
    }

    resp = requests.post(HF_BASE_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON found in response: {raw[:200]}")

    data = json.loads(json_match.group())

    data["amount"] = float(data.get("amount", 0))
    data["currency"] = str(data.get("currency", "UZS")).upper()
    if data["currency"] not in ("UZS", "USD"):
        data["currency"] = "UZS"
    data["tx_type"] = str(data.get("tx_type", "expense"))
    data["category"] = str(data.get("category", "other"))
    data.setdefault("items", [])
    data.setdefault("description", text[:200])

    return data


def _parse_with_regex(text: str) -> dict:
    t = text.lower().strip()

    items = _extract_items(t)
    amount = _extract_amount(t)
    if amount is None:
        amount = 0

    tx_type = _detect_type(t) or "expense"
    category = _detect_category(t, tx_type)
    description = _build_description(t, items, amount)

    return {
        "amount": amount,
        "currency": "UZS",
        "tx_type": tx_type,
        "category": category,
        "items": items,
        "description": description,
    }


def _extract_amount(text: str) -> float | None:
    for pattern, multiplier, strip_dots in AMOUNT_PATTERNS:
        m = re.search(pattern, text)
        if m:
            try:
                val_str = m.group(1)
                if strip_dots:
                    val_str = val_str.replace(".", "")
                val = float(val_str.replace(",", "."))
                return val * multiplier
            except (ValueError, IndexError):
                continue
    return None


def _detect_type(text: str) -> str | None:
    income_score = sum(2 for w in INCOME_WORDS if w in text)
    expense_score = sum(2 for w in EXPENSE_WORDS if w in text)

    if income_score > expense_score:
        return "income"
    if expense_score > income_score:
        return "expense"
    return None


def _detect_category(text: str, tx_type: str) -> str:
    if tx_type == "income":
        for cat, words in INCOME_CATEGORY_KW.items():
            if any(w in text for w in words):
                return cat
    else:
        for cat, words in EXPENSE_CATEGORY_KW.items():
            if any(w in text for w in words):
                return cat
    return "other"


def _extract_items(text: str) -> list[dict]:
    items = []
    for m in re.finditer(ITEM_PATTERN, text):
        try:
            qty = int(m.group(1))
            name = m.group(2).strip()
            if name and qty > 0:
                items.append({"name": name, "quantity": qty})
        except (ValueError, IndexError):
            pass
    return items


def _build_description(text: str, items: list[dict], amount: float) -> str:
    if items:
        return ", ".join(f"{i['quantity']} {i['name']}" for i in items)

    clean = re.sub(
        r'\b\d{1,3}(?:\.\d{3})*(?:\s*(?:so\'m|som|сум))?\b',
        '',
        text,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r'\b\d+\s*(k|ming|mln)\b', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\b\d{4,}\b', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:200] if clean else text[:200]
