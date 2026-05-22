import random
from typing import Optional

from .profile import ProfileStore
from .gamification import GamificationStore
from . import commentary as cm
from modules.translations import t, LANGUAGES


def _lang(l: str) -> str:
    return l if l in LANGUAGES else "uz"


class PersonalityEngine:
    def __init__(self, profile_store: ProfileStore, game_store: GamificationStore):
        self.profiles = profile_store
        self.games = game_store

    # ── Track Interaction ──

    def track_interaction(self, user_id: str, text: str = ""):
        self.profiles.record_activity(user_id)
        if text:
            self.profiles.learn_text(user_id, text)
        self._update_streak_achievements(user_id)

    def _update_streak_achievements(self, user_id: str):
        profile = self.profiles.get(user_id)
        game = self.games.get(user_id)
        streak = profile.active_streak()
        xp_map = {3: 50, 7: 100, 14: 200}
        for milestone, xp in xp_map.items():
            key = f"streak_{milestone}"
            if streak >= milestone and key not in game.achievements:
                game.achievements.append(key)
                self.games.add_xp(user_id, xp)

    # ── Transaction Commentary ──

    def after_income(self, user_id: str, amount: int, lang: str = "uz") -> Optional[str]:
        L = _lang(lang)
        user = self.profiles.get(user_id)
        game = self.games.get(user_id)

        lines = []

        comment = cm.income_comment(amount, lang=L)
        if comment:
            lines.append(comment)

        level_up = self.games.add_xp(user_id, 10)
        achievement = self.games.track_income(user_id, amount)

        if level_up > 0:
            lines.append(cm.level_up_comment(game.title, lang=L))
        if achievement:
            lines.append(cm.achievement_unlocked(achievement, lang=L))

        streak = user.active_streak()
        if streak > 0 and streak in (1, 3, 5, 7, 10, 14, 21, 30):
            sc = cm.streak_comment(streak, lang=L)
            if sc:
                lines.append(sc)

        return "\n".join(lines) if lines else None

    def after_expense(self, user_id: str, amount: int, description: str = "", lang: str = "uz") -> Optional[str]:
        L = _lang(lang)
        user = self.profiles.get(user_id)
        game = self.games.get(user_id)

        lines = []

        comment = cm.expense_comment(amount, description, lang=L)
        if comment:
            lines.append(comment)

        level_up = self.games.add_xp(user_id, 5)
        achievement = self.games.track_expense(user_id, amount)

        if level_up > 0:
            lines.append(cm.level_up_comment(game.title, lang=L))
        if achievement:
            lines.append(cm.achievement_unlocked(achievement, lang=L))

        streak = user.active_streak()
        if streak > 0 and streak in (1, 3, 5, 7, 10, 14, 21, 30):
            sc = cm.streak_comment(streak, lang=L)
            if sc:
                lines.append(sc)

        bal = cm.balance_comment(
            self._get_finance_balance(user_id), lang=L
        )
        if bal and random.random() < 0.3:
            lines.append(bal)

        return "\n".join(lines) if lines else None

    # ── Dashboard Gamification Block ──

    def gamification_block(self, user_id: str, lang: str = "uz") -> str:
        L = _lang(lang)
        game = self.games.get(user_id)
        profile = self.profiles.get(user_id)
        streak = profile.active_streak()

        lines = [
            t("general", "level", L, level=game.level, title=game.title),
            t("general", "xp", L, xp=game.xp),
            t("general", "streak", L, streak=streak),
        ]
        if game.achievements:
            achievement_names = []
            for key in game.achievements[:3]:
                info = cm.achievement_unlocked(key, lang=L)
                name = info.split(":")[-1].strip() if ":" in info else key
                achievement_names.append(name)
            if achievement_names:
                lines.append(t("general", "achievements", L, achievements=", ".join(achievement_names)))
        return "\n".join(lines)

    # ── Finance balance hook (set externally) ──

    def set_balance_provider(self, fn):
        self._balance_fn = fn

    def _get_finance_balance(self, user_id: str) -> int:
        if hasattr(self, "_balance_fn") and self._balance_fn:
            try:
                return self._balance_fn(user_id)
            except Exception:
                return 0
        return 0
