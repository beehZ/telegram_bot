import math


class CalorieCalculator:
    @staticmethod
    def bmr_mifflin(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
        if gender.lower() in ("m", "male", "erkak"):
            return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    @staticmethod
    def tdee(bmr: float, activity_level: str) -> float:
        mult = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }.get(activity_level, 1.2)
        return bmr * mult

    @staticmethod
    def calculate(
        weight_kg: float,
        height_cm: float,
        age: int,
        gender: str,
        activity: str,
        goal: str,
        goal_weight: float = None,
        fat_loss_speed: str = "moderate",
    ) -> dict:
        bmr = CalorieCalculator.bmr_mifflin(weight_kg, height_cm, age, gender)
        tdee = CalorieCalculator.tdee(bmr, activity)

        surplus = 0
        deficit = 0
        protein_per_kg = 1.6

        if goal in ("muscle_gain", "weight_gain", "lean_bulk"):
            surplus = 300 if goal == "lean_bulk" else 500
            protein_per_kg = 2.0 if goal == "muscle_gain" else 1.8
            target_cal = tdee + surplus
        elif goal == "weight_loss":
            speed_map = {"slow": 200, "moderate": 400, "fast": 600}
            deficit = speed_map.get(fat_loss_speed, 400)
            protein_per_kg = 2.2
            target_cal = tdee - deficit
        else:
            target_cal = tdee

        protein_g = round(weight_kg * protein_per_kg)
        fat_g = round(target_cal * 0.25 / 9)
        carb_g = round((target_cal - protein_g * 4 - fat_g * 9) / 4)
        water_ml = int(weight_kg * 35)
        timeline_weeks = CalorieCalculator._timeline(
            weight_kg, goal_weight or weight_kg, deficit or surplus, goal
        )

        return {
            "bmr": round(bmr),
            "tdee": round(tdee),
            "target_calories": round(target_cal),
            "protein_g": max(protein_g, 50),
            "fat_g": max(fat_g, 30),
            "carb_g": max(carb_g, 50),
            "water_ml": water_ml,
            "surplus": surplus,
            "deficit": deficit,
            "timeline_weeks": timeline_weeks,
            "protein_per_kg": protein_per_kg,
            "recommendation": CalorieCalculator._recommendation(goal, target_cal, protein_g),
        }

    @staticmethod
    def _timeline(current: float, target: float, delta: int, goal: str) -> int:
        if delta == 0:
            return 0
        # ~0.5kg per week for fat loss, ~0.25kg per week for muscle gain
        if goal in ("muscle_gain", "weight_gain", "lean_bulk"):
            weekly_change = 0.25
        else:
            weekly_change = 0.5
        diff = abs(target - current)
        return max(1, round(diff / weekly_change))

    @staticmethod
    def _recommendation(goal: str, cal: int, protein: int) -> str:
        if goal in ("muscle_gain", "weight_gain", "lean_bulk"):
            return (
                f"Kuniga {cal} kcal va {protein}g protein mushak qurish uchun optimal. "
                f"Proteinni har ovqatda teng taqsimlang."
            )
        if goal == "weight_loss":
            return (
                f"Kuniga {cal} kcal bilan haftasiga ~0.5kg yo'qotishingiz mumkin. "
                f"{protein}g protein mushakni saqlashga yordam beradi."
            )
        return f"Kuniga {cal} kcal vaznni saqlash uchun."
