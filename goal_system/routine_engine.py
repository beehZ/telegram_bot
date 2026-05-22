import logging
from typing import Optional

logger = logging.getLogger("routine_engine")

BASE_SLOTS = [
    ("05:00", "Wake Up", "general"),
    ("05:30", "Morning Preparation", "general"),
    ("06:00", None, None),
    ("08:00", None, None),
    ("09:00", None, None),
    ("11:00", None, None),
    ("13:00", None, None),
    ("14:00", None, None),
    ("15:00", None, None),
    ("17:30", None, None),
    ("19:30", None, None),
    ("20:00", None, None),
    ("21:00", "Reflection / Planning", "general"),
    ("22:00", None, None),
]

GOAL_SLOT_MAP = {
    "gain_muscle":   [("06:00", "\U0001f3cb\ufe0f Gym")],
    "lose_weight":   [("06:00", "\U0001f3cb\ufe0f Gym")],
    "gain_weight":   [("06:00", "\U0001f3cb\ufe0f Gym")],
    "cardio":        [("06:00", "\U0001f3cb\ufe0f Cardio")],
    "math":          [("08:00", "\U0001f4d8 Math Lesson")],
    "english":       [("11:00", "\U0001f4d6 English Lesson")],
    "programming":   [("14:00", "\U0001f4bb Coding Session")],
    "ml_ai":         [("14:00", "\U0001f916 ML/AI Study")],
    "reading":       [("13:00", "\U0001f4da Reading Time")],
    "business":      [("15:00", "\U0001f4bc Business Development")],
    "freelancing":   [("15:00", "\U0001f4bc Freelancing Work")],
    "content_creation": [("15:00", "\U0001f3ac Content Creation")],
    "social_skills": [("15:00", "\U0001f4f1 Social Skills Practice")],
    "looksmaxing":   [("11:00", "\u2728 Looksmaxing Routine")],
    "productivity":  [("20:00", "\U0001f9e0 Productivity Session")],
    "focus":         [("20:00", "\U0001f3af Focus Training")],
    "discipline":    [("20:00", "\u26a1 Discipline Practice")],
    "meditation":    [("20:00", "\U0001f9d8 Meditation")],
    "dopamine_detox": [("20:00", "\U0001f9f9 Dopamine Detox")],
    "better_sleep":  [("22:00", "\U0001f634 Sleep Preparation")],
    "healthy_eating": [("09:00", "\U0001f957 Healthy Meal"), ("19:30", "\U0001f957 Healthy Meal")],
}

SLOT_PRIORITY = {
    "gain_muscle": 10,
    "lose_weight": 10,
    "gain_weight": 10,
    "cardio": 10,
    "math": 20,
    "english": 40,
    "programming": 30,
    "ml_ai": 30,
    "reading": 50,
    "business": 20,
    "freelancing": 20,
    "content_creation": 20,
    "social_skills": 60,
    "looksmaxing": 25,
    "productivity": 30,
    "focus": 30,
    "discipline": 30,
    "meditation": 50,
    "dopamine_detox": 50,
    "better_sleep": 10,
    "healthy_eating": 20,
}

DEFAULT_FILLERS = {
    "06:00": "Free Time / Stretch",
    "08:00": "Self-Study Time",
    "09:00": "Breakfast",
    "11:00": "Personal Development",
    "13:00": "Lunch / Free Time",
    "14:00": "Skill Development",
    "15:00": "Work / Projects",
    "17:30": "Walk / Recovery",
    "19:30": "Dinner",
    "20:00": "Evening Relaxation",
    "22:00": "\U0001f634 Sleep Preparation",
}


class RoutineEngine:
    def generate(self, selected_goals: list[str]) -> list[dict]:
        slots = {}
        for time, title, cat in BASE_SLOTS:
            if title:
                slots[time] = {"title": title, "category": cat, "goal_key": None}
            else:
                slots[time] = {"title": None, "category": None, "goal_key": None}

        assignments: dict[str, list[tuple[str, str, int]]] = {}
        for goal_key in selected_goals:
            mappings = GOAL_SLOT_MAP.get(goal_key, [])
            for time, title in mappings:
                if time not in assignments:
                    assignments[time] = []
                assignments[time].append((goal_key, title, SLOT_PRIORITY.get(goal_key, 99)))

        if "social_skills" in selected_goals:
            has_15_conflict = any(
                gk != "social_skills"
                for gk, _, _ in assignments.get("15:00", [])
            )
            if has_15_conflict:
                assignments["15:00"] = [
                    item for item in assignments.get("15:00", [])
                    if item[0] != "social_skills"
                ]
                if not assignments["15:00"]:
                    del assignments["15:00"]
                if "17:30" not in assignments:
                    assignments["17:30"] = []
                assignments["17:30"].append(("social_skills", "\U0001f4f1 Social Skills Practice", SLOT_PRIORITY.get("social_skills", 60)))

        resolved = {}
        for time, items in sorted(assignments.items()):
            if not items:
                continue
            items.sort(key=lambda x: x[2])
            best = items[0]
            resolved[time] = {"title": best[1], "goal_key": best[0]}

        for time, data in slots.items():
            if time in resolved:
                data["title"] = resolved[time]["title"]
                data["goal_key"] = resolved[time]["goal_key"]
            elif data["title"] is None:
                data["title"] = DEFAULT_FILLERS.get(time, "")
                data["category"] = "general"

        result = []
        for time in sorted(slots.keys()):
            data = slots[time]
            goal_key = data.get("goal_key")
            category = goal_key if goal_key else data.get("category", "general")
            result.append({
                "time": time,
                "title": data["title"],
                "category": category,
                "goal_key": goal_key,
            })

        return result

    def format_routine_text(self, routine: list[dict], lang: str = "uz") -> str:
        headers = {
            "uz": "\U0001f4c5 *KUNLIK TARTIBINGIZ*",
            "ru": "\U0001f4c5 *\u0412\u0410\u0428 \u0414\u041d\u0415\u0412\u041d\u041e\u0419 \u0420\u0410\u0421\u041f\u041e\u0420\u042f\u0414\u041e\u041a*",
            "en": "\U0001f4c5 *DAILY ROUTINE*",
        }
        lines = [headers.get(lang, headers["en"])]
        for slot in routine:
            if slot["title"]:
                lines.append(f"{slot['time']} \u2013 {slot['title']}")
        return "\n".join(lines)

    def format_tasks_text(self, task_content: dict[str, list[str]], lang: str = "uz") -> str:
        lines = []
        for goal_key, tasks in task_content.items():
            if not tasks:
                continue
            lines.append(f"\n\U0001f4cb **{goal_key.replace('_', ' ').title()} Tasks**")
            for t in tasks:
                lines.append(f"* {t}")
        return "\n".join(lines)
