import re
from typing import Optional


FOOD_UNIT_PATTERNS = [
    (r'(\d+(?:[.,]\d+)?)\s*(ml|liter|litr|l)\s+(.+)', 1, 'ml'),
    (r'(\d+(?:[.,]\d+)?)\s*(kg|kilo)\s+(.+)', 1, 'kg'),
    (r'(\d+(?:[.,]\d+)?)\s*(gr|g|gram)\s+(.+)', 1, 'g'),
    (r'(\d+(?:[.,]\d+)?)\s*(stakan|cup|glass|chashka|piyola)\s+(.+)', 1, 'cup'),
    (r'(\d+(?:[.,]\d+)?)\s*(qoshiq|spoon|tbsp|tsp|osh qoshiq|choy qoshiq)\s+(.+)', 1, 'spoon'),
    (r'(\d+(?:[.,]\d+)?)\s*(dona|don|ta|piece|pcs)\s+(.+)', 1, 'piece'),
    (r'(\d+(?:[.,]\d+)?)\s*(slices|bo\'lak|tilim|dilim)\s+(.+)', 1, 'slice'),
    (r'(\d+(?:[.,]\d+)?)\s*(bottle|shisha|butilka)\s+(.+)', 1, 'bottle'),
    (r'(\d+)\s*ta\s+(.+)', 1, 'piece'),
    (r'(\d+)\s*dona\s+(.+)', 1, 'piece'),
    (r'(\d+)\s*don\s+(.+)', 1, 'piece'),
    (r'(\d+(?:[.,]\d+)?)\s+(.+)', 1, 'piece'),
]

PLAIN_FOOD_PATTERN = r'(.+)'

SEPARATORS = r'\s*(?:va|,|\s*,\s*|\s+hamda|\s+bilan|\s+and)\s*'


class ParsedFoodItem:
    def __init__(self, food: str, amount: float = 1, unit: str = 'piece', raw: str = ''):
        self.food = food.strip().lower()
        self.amount = amount
        self.unit = unit
        self.raw = raw.strip()

    def __repr__(self):
        return f"ParsedFoodItem(food='{self.food}', amount={self.amount}, unit='{self.unit}')"


class FoodParser:

    @staticmethod
    def split_items(text: str) -> list[str]:
        parts = re.split(SEPARATORS, text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def parse_item(text: str) -> Optional[ParsedFoodItem]:
        t = text.strip().lower()

        for pattern, amount_group, unit in FOOD_UNIT_PATTERNS:
            m = re.match(pattern, t)
            if m:
                try:
                    amount = float(m.group(1).replace(",", "."))
                except ValueError:
                    amount = 1
                food_name = (m.group(3) if m.lastindex and m.lastindex >= 3 else m.group(2)).strip()
                return ParsedFoodItem(food=food_name, amount=amount, unit=unit, raw=text)

        return ParsedFoodItem(food=t, amount=1, unit='piece', raw=text)

    @classmethod
    def parse(cls, text: str) -> list[ParsedFoodItem]:
        items = cls.split_items(text)
        result = []
        for item in items:
            parsed = cls.parse_item(item)
            if parsed:
                result.append(parsed)
        return result

    @staticmethod
    def is_likely_food(text: str) -> bool:
        t = text.lower().strip()

        non_food_markers = [
            "bajarildi", "done", "completed", "finished", "tugadi",
            "mission", "progress", "streak", "goal", "profile",
            "hello", "salom", "hi", "hey",
        ]
        for m in non_food_markers:
            if m in t:
                return False

        food_keywords = [
            "osh", "non", "tuxum", "coffee", "cola", "burger", "pizza",
            "salad", "apple", "banana", "rice", "chicken", "soup",
            "shurva", "manti", "somsa", "lagman", "kebab", "shashlik",
            "plov", "sut", "choy", "water", "juice", "cake", "bread",
            "butter", "cheese", "meat", "fish", "egg", "milk", "yogurt",
            "pasta", "spaghetti", "steak", "sandwich", "wrap", "noodle",
            "porridge", "oatmeal", "cereal", "toast", "avocado", "broccoli",
            "spinach", "tomato", "potato", "carrot", "chocolate", "cookie",
            "donut", "ice cream", "smoothie", "protein", "shake",
            "kartoshka", "guruch", "mosh", "loviya", "sabzavot",
            "go'sht", "gosht", "mol", "qovurma", "kabob",
            "tea", "kofe", "qatiq", "kefir", "qaymoq",
        ]
        for fk in food_keywords:
            if fk in t:
                return True

        items = FoodParser.parse(t)
        if items:
            return True

        words = t.split()
        if 1 <= len(words) <= 5:
            has_food_indicators = bool(re.search(r'\b(ml|kg|gr|g|dona|don|ta|stakan|qoshiq)\b', t))
            if has_food_indicators:
                return True
            if any(len(w) > 2 for w in words):
                return True

        return False
