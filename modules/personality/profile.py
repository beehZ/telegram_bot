from datetime import datetime, timezone
from typing import Optional


class UserProfileData:
    __slots__ = (
        "user_id", "tone", "humor_level", "slang_usage",
        "motivational_style", "response_style",
        "interests", "keywords", "last_active",
        "activity_days",
    )

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.tone = "casual"
        self.humor_level = 3
        self.slang_usage = 2
        self.motivational_style = "chill"
        self.response_style = "energetic"
        self.interests: list[str] = []
        self.keywords: dict[str, int] = {}
        self.last_active: str = ""
        self.activity_days: set[str] = set()

    def record_activity(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.last_active = today
        self.activity_days.add(today)

    def active_streak(self) -> int:
        if not self.activity_days:
            return 0
        sorted_days = sorted(self.activity_days, reverse=True)
        streak = 0
        from datetime import timedelta
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        check = today
        for day in sorted_days:
            if day == check:
                streak += 1
                dt = datetime.strptime(check, "%Y-%m-%d")
                check = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                break
        return streak

    def longest_streak(self) -> int:
        if not self.activity_days:
            return 0
        sorted_days = sorted(self.activity_days)
        longest = 1
        current = 1
        from datetime import timedelta
        for i in range(1, len(sorted_days)):
            prev = datetime.strptime(sorted_days[i - 1], "%Y-%m-%d")
            curr = datetime.strptime(sorted_days[i], "%Y-%m-%d")
            if (curr - prev).days == 1:
                current += 1
                longest = max(longest, current)
            else:
                current = 1
        return longest

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "tone": self.tone,
            "humor_level": self.humor_level,
            "slang_usage": self.slang_usage,
            "motivational_style": self.motivational_style,
            "response_style": self.response_style,
            "interests": self.interests,
            "keywords": self.keywords,
            "last_active": self.last_active,
            "activity_days": list(self.activity_days),
        }


class ProfileStore:
    def __init__(self):
        self._users: dict[str, UserProfileData] = {}

    def get(self, user_id: str) -> UserProfileData:
        if user_id not in self._users:
            self._users[user_id] = UserProfileData(user_id)
        return self._users[user_id]

    def record_activity(self, user_id: str):
        self.get(user_id).record_activity()

    def active_streak(self, user_id: str) -> int:
        return self.get(user_id).active_streak()

    def longest_streak(self, user_id: str) -> int:
        return self.get(user_id).longest_streak()

    def learn_text(self, user_id: str, text: str):
        profile = self.get(user_id)
        words = text.lower().split()
        for word in words:
            if len(word) > 3:
                profile.keywords[word] = profile.keywords.get(word, 0) + 1

        interest_keywords = {
            "bmw", "merc", "audi", "tesla", "car", "cars", "mashina",
            "gym", "fitness", "workout", "training", "dumbbell",
            "business", "biznes", "startup", "project",
            "game", "gaming", "pubg", "cs", "valorant", "lol",
            "food", "ovqat", "restaurant", "kafe",
        }
        for word in words:
            clean = word.strip(".,!?")
            if clean in interest_keywords and clean not in profile.interests:
                profile.interests.append(clean)

    def count(self) -> int:
        return len(self._users)
