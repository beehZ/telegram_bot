import re
from typing import Optional, Tuple


class NumberParser:
    CURRENCY_RE = re.compile(
        r"\b(so'm|som|sums?|usd|eur|rub|сум|сом)\b",
        re.IGNORECASE,
    )

    SUFFIX_MAP = {"k": 1000, "m": 1000000, "mln": 1000000, "million": 1000000}

    AMOUNT_PREFIX_RE = re.compile(
        r'^(\d[\d\s.,]*(?:k|m|mln|million)?)\s+(.+)',
        re.IGNORECASE,
    )

    @classmethod
    def parse_amount(cls, text: str) -> Optional[int]:
        if not text or not isinstance(text, str):
            return None
        t = text.strip()
        if not t:
            return None

        t = cls.CURRENCY_RE.sub("", t).strip()
        if not t:
            return None

        t = t.replace(",", ".")
        t = re.sub(r"\s+", "", t)
        if not t:
            return None

        if not re.fullmatch(r"\d[\d.]*(?:[km]|mln|million)?", t, re.IGNORECASE):
            return None

        t_lower = t.lower()

        suffix = None
        num_part = t_lower
        for s in ("million", "mln", "m", "k"):
            if t_lower.endswith(s):
                suffix = s
                num_part = t_lower[: -len(s)]
                break

        if suffix:
            try:
                val = float(num_part)
            except ValueError:
                return None
            multiplier = cls.SUFFIX_MAP.get(suffix, 1000)
            result = int(val * multiplier)
            return result if result > 0 else None

        clean = num_part.replace(".", "")
        if not clean.isdigit():
            return None
        result = int(clean)
        return result if result > 0 else None

    @classmethod
    def _has_meaningful_text(cls, t: str) -> bool:
        t = t.strip()
        if not t:
            return False
        if re.search(r"[a-zA-Zа-яА-ЯёЁöÖğĞüÜıİşŞçÇ]", t):
            return True
        return False

    @classmethod
    def parse_expense(cls, text: str) -> Tuple[Optional[int], str]:
        if not text or not isinstance(text, str):
            return (None, "")
        t = text.strip()
        if not t:
            return (None, "")

        t = cls.CURRENCY_RE.sub("", t).strip()
        if not t:
            return (None, "")

        m = cls.AMOUNT_PREFIX_RE.match(t)
        if m:
            raw_amount = m.group(1).strip()
            description = m.group(2).strip()
            amount = cls.parse_amount(raw_amount)
            if amount is not None:
                return (amount, description)

        amount = cls.parse_amount(t)
        if amount is not None:
            return (amount, "No description")

        if cls._has_meaningful_text(t):
            return (None, t)

        return (None, "")
