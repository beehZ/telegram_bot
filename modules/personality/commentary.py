import random
from typing import Optional

from modules.translations import t, t_nested, T, LANGUAGES

CATEGORY_KEYWORDS = {
    "food": ["ovqat", "non", "taom", "kafe", "restoran", "oshxona", "yegulik", "food", "еда", "продукты"],
    "transport": ["taxi", "transport", "benzin", "yo'l", "mashina", "metro", "bus", "gaz", "такси", "бензин"],
    "game_entertainment": ["game", "o'yin", "pubg", "cs", "valoran", "игра", "развлечения"],
    "health": ["dori", "doctor", "vrach", "bolnitsa", "health", "sog'liq", "здоровье", "врач", "аптека"],
}


def _detect_category(description: str) -> Optional[str]:
    desc_lower = description.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(w in desc_lower for w in keywords):
            return cat
    return None


def _lang(l: str) -> str:
    return l if l in LANGUAGES else "uz"





def income_comment(amount: int, lang: str = "uz") -> str:
    L = _lang(lang)
    if amount >= 1_000_000:
        return random.choice(T["commentary"][L]["income"]["huge"])
    if amount >= 500_000:
        return random.choice(T["commentary"][L]["income"]["large"])
    if amount >= 100_000:
        return random.choice(T["commentary"][L]["income"]["medium"])
    return random.choice(T["commentary"][L]["income"]["small"])


def expense_comment(amount: int, description: str = "", lang: str = "uz") -> str:
    L = _lang(lang)
    cat = _detect_category(description) if description else None
    if cat and cat in T["commentary"][L]["expense"]:
        return random.choice(T["commentary"][L]["expense"][cat])
    if amount >= 500_000:
        return random.choice(T["commentary"][L]["expense"]["huge"])
    if amount >= 100_000:
        return random.choice(T["commentary"][L]["expense"]["large"])
    if amount >= 50_000:
        return random.choice(T["commentary"][L]["expense"]["medium"])
    return random.choice(T["commentary"][L]["expense"]["small"])


def balance_comment(balance: int, lang: str = "uz") -> str:
    L = _lang(lang)
    if balance <= 0:
        return random.choice(T["commentary"][L]["balance"]["critical"])
    if balance < 50_000:
        return random.choice(T["commentary"][L]["balance"]["low"])
    if balance < 500_000:
        return random.choice(T["commentary"][L]["balance"]["good"])
    return random.choice(T["commentary"][L]["balance"]["great"])


def streak_comment(streak: int, lang: str = "uz") -> Optional[str]:
    L = _lang(lang)
    milestones = sorted(int(k) for k in T["commentary"][L]["streak"].keys())
    for m in reversed(milestones):
        if streak >= m:
            return random.choice(T["commentary"][L]["streak"][str(m)])
    return None


def achievement_unlocked(key: str, lang: str = "uz") -> str:
    L = _lang(lang)
    return T["commentary"][L]["achievements"].get(key, f"\U0001f389 {t('general', 'level_up', L)}")


def level_up_comment(title: str, lang: str = "uz") -> str:
    L = _lang(lang)
    msg = random.choice(T["commentary"][L]["level_up"])
    return msg.replace("{title}", title)
