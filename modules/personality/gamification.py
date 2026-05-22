import random
from datetime import datetime, timezone
from typing import Optional


LEVELS = [
    (0, "Budget Rookie"),
    (100, "Money Saver"),
    (300, "Cash Manager"),
    (600, "Finance Bro"),
    (1000, "Money Grinder"),
    (1500, "Wealth Builder"),
    (2500, "Discipline Monster"),
    (4000, "Financial Genius"),
    (6000, "Money Master"),
    (8500, "Legend"),
]

ACHIEVEMENTS = {
    "first_tx": {"name": "First Step", "desc": "First transaction recorded", "xp": 50},
    "first_income": {"name": "Money Coming", "desc": "First income added", "xp": 30},
    "first_expense": {"name": "Money Going", "desc": "First expense added", "xp": 20},
    "streak_3": {"name": "On Fire", "desc": "3-day streak", "xp": 50},
    "streak_7": {"name": "Unstoppable", "desc": "7-day streak", "xp": 100},
    "streak_14": {"name": "Legendary", "desc": "14-day streak", "xp": 200},
    "big_spender": {"name": "Big Spender", "desc": "Single expense over 500k", "xp": 40},
    "big_earner": {"name": "Big Earner", "desc": "Single income over 1m", "xp": 40},
    "transactions_5": {"name": "Saver", "desc": "5 transactions tracked", "xp": 30},
    "transactions_10": {"name": "Tracker", "desc": "10 transactions tracked", "xp": 50},
    "transactions_20": {"name": "Dedicated", "desc": "20 transactions tracked", "xp": 80},
}


class GamificationData:
    __slots__ = (
        "user_id", "xp", "level", "total_income_tx", "total_expense_tx",
        "achievements", "highest_expense", "highest_income",
    )

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.xp = 0
        self.level = 1
        self.total_income_tx = 0
        self.total_expense_tx = 0
        self.achievements: list[str] = []
        self.highest_expense = 0
        self.highest_income = 0

    @property
    def title(self) -> str:
        for xp_req, title in reversed(LEVELS):
            if self.xp >= xp_req:
                return title
        return "Budget Rookie"

    @property
    def next_level_xp(self) -> int:
        for i, (xp_req, _) in enumerate(LEVELS):
            if xp_req > self.xp:
                return xp_req
        return LEVELS[-1][0]

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "xp": self.xp,
            "level": self.level,
            "title": self.title,
            "total_income_tx": self.total_income_tx,
            "total_expense_tx": self.total_expense_tx,
            "achievements": self.achievements,
            "highest_expense": self.highest_expense,
            "highest_income": self.highest_income,
        }


class GamificationStore:
    def __init__(self):
        self._users: dict[str, GamificationData] = {}

    def get(self, user_id: str) -> GamificationData:
        if user_id not in self._users:
            self._users[user_id] = GamificationData(user_id)
        return self._users[user_id]

    def add_xp(self, user_id: str, amount: int) -> int:
        g = self.get(user_id)
        old_level = g.level
        g.xp += amount
        new_level = 1
        for xp_req, _ in LEVELS:
            if g.xp >= xp_req:
                new_level = LEVELS.index((xp_req, _)) + 1
        g.level = new_level
        return new_level - old_level

    def track_income(self, user_id: str, amount: int) -> Optional[str]:
        g = self.get(user_id)
        g.total_income_tx += 1
        if amount > g.highest_income:
            g.highest_income = amount
        return self._check_achievements(user_id)

    def track_expense(self, user_id: str, amount: int) -> Optional[str]:
        g = self.get(user_id)
        g.total_expense_tx += 1
        if amount > g.highest_expense:
            g.highest_expense = amount
        return self._check_achievements(user_id)

    def _check_achievements(self, user_id: str) -> Optional[str]:
        g = self.get(user_id)
        total_tx = g.total_income_tx + g.total_expense_tx
        unlocks = []

        checks = [
            ("first_tx", total_tx >= 1),
            ("first_income", g.total_income_tx >= 1),
            ("first_expense", g.total_expense_tx >= 1),
            ("big_spender", g.highest_expense >= 500000),
            ("big_earner", g.highest_income >= 1000000),
            ("transactions_5", total_tx >= 5),
            ("transactions_10", total_tx >= 10),
            ("transactions_20", total_tx >= 20),
        ]

        for key, cond in checks:
            if cond and key not in g.achievements:
                g.achievements.append(key)
                self.add_xp(user_id, ACHIEVEMENTS[key]["xp"])
                unlocks.append(key)

        if unlocks:
            return random.choice(unlocks)
        return None

    def get_new_achievements(self, user_id: str) -> list[str]:
        g = self.get(user_id)
        return g.achievements

    def count(self) -> int:
        return len(self._users)
