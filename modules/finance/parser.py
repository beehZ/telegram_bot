import logging
import re
from typing import Optional

from services.nlp_parser import parse_money_text

logger = logging.getLogger("finance_parser")

AMOUNT_PATTERNS = [
    (r'(\d{1,3}(?:\.\d{3})+)\s*(?:so\'m|som|сум)', 1, True),
    (r'(\d+(?:[.,]\d+)?)\s*(mln|million|млн)', 1_000_000, False),
    (r'(\d+(?:[.,]\d+)?)\s*(ming|минг)\s*(?:so\'m|som|сум)?', 1_000, False),
    (r'(\d+(?:[.,]\d+)?)\s*k\b', 1_000, False),
    (r'(\d+(?:[.,]\d+)?)\s*(?:so\'m|som|сум)', 1, False),
    (r'\b(\d{4,})\b', 1, False),
]

EXPENSE_VERBS = [
    "ketdi", "berdim", "sarfladim", "xarajat", "to'ladim", "toladim",
    "oldim", "sotib oldim", "ishlatdim", "chiqdim", "berib yubordim",
    "to'lov", "tolov", "harajat", "qildim",
]

INCOME_VERBS = [
    "tushdi", "oldim", "foyda", "daromad", "oylik", "maosh",
    "ish haqi", "ishhaki", "qaytardi", "qaytdi", "kelib tushdi",
    "yutdim", "topdim",
]

EXPENSE_CATEGORIES = {
    "food": ["ovqat", "taom", "nonushta", "tushlik", "kechki", "oshxona",
             "kafe", "restoran", "non", "sut", "choy", "go'sht", "gosht",
             "sabzavot", "meva", "yegulik", "oziq"],
    "transport": ["benzin", "taxi", "transport", "yo'l", "yol", "avtobus",
                  "metro", "mashina", "gaz", "bus", "poezd"],
    "shopping": ["kiyim", "poyabzal", "do'kon", "dokon", "magazin",
                 "bozor", "narsa", "buyum"],
    "health": ["dorixona", "shifokor", "dori", "vrach", "bolnitsa",
               "kasal", "kasalxona", "tabletka", "doctor"],
    "education": ["o'qish", "oqish", "kurs", "dars", "talim", "ta'lim",
                  "maktab", "univer", "kitob", "o'quv", "oquv"],
    "rent": ["ijara", "kvartira", "kommunal", "elektr", "gaz", "suv",
             "uy", "shar", "arenda"],
    "gaming": ["o'yin", "oyin", "game", "pubg", "cs", "valoran"],
    "family": ["oila", "bola", "farzand", "uy"],
    "phone": ["telefon", "gsm", "uzmobile", "beeline", "ucell", "mobiuz",
              "internet", "tarif", "sim"],
}

INCOME_CATEGORIES = {
    "salary": ["oylik", "maosh", "ish haqi", "ishhaki", "oklad", "zam",
               "ish haqqi", "lavozim"],
    "business": ["biznes", "daromad", "foyda", "savdo", "tijorat",
                  "mijoz", "zakaz"],
    "gift": ["sovg'a", "sovga", "hadya", "gift", "sovga"],
    "freelance": ["freelans", "freelance", "frilans", "upwork",
                   "fiverr", "remote"],
    "debt_return": ["qarz", "qaytardi", "qaytdi", "berdi", "qarzni",
                     "qarzdor"],
}

MONEY_HINT_WORDS = [
    "ming", "mln", "million", "so'm", "som", "sum", "k", "ming so'm",
    "pul", "naqd", "karta", "plastik", "balans",
]


class FinanceParserResult:
    def __init__(self, amount: Optional[float] = None, tx_type: Optional[str] = None,
                 category: Optional[str] = None, description: str = "",
                 confidence: float = 0.0, raw_text: str = "",
                 items: Optional[list] = None):
        self.amount = amount
        self.tx_type = tx_type
        self.category = category
        self.description = description
        self.confidence = confidence
        self.raw_text = raw_text
        self.items = items or []

    @property
    def is_valid(self) -> bool:
        return self.amount is not None and self.amount > 0 and self.tx_type is not None


class FinanceParser:

    @staticmethod
    def extract_amount(text: str) -> Optional[float]:
        t = text.lower().strip()
        for pattern, multiplier, strip_dots in AMOUNT_PATTERNS:
            m = re.search(pattern, t)
            if m:
                try:
                    val_str = m.group(1)
                    if strip_dots:
                        val_str = val_str.replace(".", "")
                    val = float(val_str.replace(",", "."))
                    return val * multiplier
                except ValueError:
                    continue
        return None

    @staticmethod
    def detect_type(text: str) -> Optional[str]:
        t = text.lower()
        income_score = sum(1 for v in INCOME_VERBS if v in t)
        expense_score = sum(1 for v in EXPENSE_VERBS if v in t)

        for v in INCOME_VERBS:
            if v in t:
                income_score += 2

        for v in EXPENSE_VERBS:
            if v in t:
                expense_score += 2

        if income_score > expense_score:
            return "income"
        if expense_score > income_score:
            return "expense"
        return None

    @staticmethod
    def detect_category(text: str, tx_type: str) -> str:
        t = text.lower()
        if tx_type == "income":
            best_cat = "other"
            best_score = 0
            for cat, keywords in INCOME_CATEGORIES.items():
                score = sum(2 for kw in keywords if kw in t)
                if score > best_score:
                    best_score = score
                    best_cat = cat
            return best_cat
        else:
            best_cat = "other"
            best_score = 0
            for cat, keywords in EXPENSE_CATEGORIES.items():
                score = sum(2 for kw in keywords if kw in t)
                if score > best_score:
                    best_score = score
                    best_cat = cat
            return best_cat

    @staticmethod
    def has_money_hints(text: str) -> bool:
        t = text.lower()
        count = sum(1 for h in MONEY_HINT_WORDS if h in t)
        has_digits = bool(re.search(r'\d{2,}', t))
        return count >= 1 or has_digits

    @classmethod
    def parse(cls, text: str) -> FinanceParserResult:
        if not cls.has_money_hints(text):
            return FinanceParserResult(confidence=0.0, raw_text=text)

        # Try AI-powered NLP parsing first
        try:
            nlp_result = parse_money_text(text)
            amount = nlp_result.get("amount", 0)
            tx_type = nlp_result.get("tx_type")
            category = nlp_result.get("category", "other")
            description = nlp_result.get("description", text[:200])

            if amount > 0 and tx_type:
                return FinanceParserResult(
                    amount=amount,
                    tx_type=tx_type,
                    category=category,
                    description=description,
                    confidence=0.9,
                    raw_text=text,
                    items=nlp_result.get("items", []),
                )
        except Exception as e:
            logger.warning("AI parsing failed, falling back to regex: %s", e)

        # Fallback to regex
        amount = cls.extract_amount(text)
        if amount is None:
            return FinanceParserResult(confidence=0.0, raw_text=text)

        tx_type = cls.detect_type(text)
        if tx_type is None:
            tx_type = "expense"

        category = cls.detect_category(text, tx_type)
        description = text.strip()

        confidence = 0.5
        if amount is not None and amount > 0:
            confidence += 0.2
        if tx_type is not None:
            confidence += 0.2
        if category != "other":
            confidence += 0.1

        return FinanceParserResult(
            amount=amount,
            tx_type=tx_type,
            category=category,
            description=description,
            confidence=min(confidence, 1.0),
            raw_text=text,
        )
