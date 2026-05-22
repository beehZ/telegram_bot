import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("discipline_engine")

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

DIFFICULTY_XP = {"easy": 10, "medium": 25, "hard": 50}


class DisciplineEngine:
    def __init__(self, db):
        self.db = db

    async def award_task_xp(self, uid: int, difficulty: str) -> int:
        base = DIFFICULTY_XP.get(difficulty, 25)
        bonus = 0
        disc = await self.db.get_discipline(uid)
        if disc["streak"] >= 7:
            bonus = int(base * 0.2)
        elif disc["streak"] >= 30:
            bonus = int(base * 0.5)
        total_xp = base + bonus
        await self.db.award_xp(uid, total_xp)
        return total_xp

    async def update_streak(self, uid: int):
        disc = await self.db.get_discipline(uid)
        today_str = date.today().strftime("%Y-%m-%d")
        last = disc.get("last_active_date", "")
        current = disc["streak"]
        longest = disc["longest_streak"]

        if last == today_str:
            return current

        yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last == yesterday_str:
            current += 1
        elif last:
            current = 1
        else:
            current = 1

        longest = max(longest, current)
        await self.db.update_discipline(
            uid,
            streak=current,
            longest_streak=longest,
            last_active_date=today_str,
        )
        return current

    async def update_discipline_score(self, uid: int):
        disc = await self.db.get_discipline(uid)
        total = disc["total_completed"] + disc["total_skipped"] + disc["total_delayed"]
        if total == 0:
            score = 50
        else:
            completion_rate = disc["total_completed"] / total
            delay_penalty = disc["total_delayed"] * 0.05
            skip_penalty = disc["total_skipped"] * 0.15
            raw = (completion_rate * 100) - (delay_penalty * 100) - (skip_penalty * 100)
            raw += disc["streak"] * 2
            score = max(0, min(100, int(raw)))
        await self.db.update_discipline(uid, discipline_score=score)
        return score

    async def _calculate_task_xp(self, uid: int, difficulty: str) -> int:
        base = DIFFICULTY_XP.get(difficulty, 25)
        disc = await self.db.get_discipline(uid)
        bonus = 0
        if disc["streak"] >= 30:
            bonus = int(base * 0.5)
        elif disc["streak"] >= 7:
            bonus = int(base * 0.2)
        return base + bonus

    async def log_task_completion(self, uid: int, routine_id: int, status: str):
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        routine = await self.db.get_routine(routine_id)
        difficulty = routine["difficulty"] if routine else "medium"

        xp = 0
        if status in ("completed", "partial"):
            raw_xp = await self._calculate_task_xp(uid, difficulty)
            xp = max(1, raw_xp // 2) if status == "partial" else raw_xp
            await self.db.award_xp(uid, xp)
            await self.db.log_task(uid, routine_id, today, status, xp)
            disc = await self.db.get_discipline(uid)
            await self.db.update_discipline(
                uid,
                total_completed=disc["total_completed"] + 1,
            )
            await self.update_streak(uid)
        elif status == "skipped":
            await self.db.log_task(uid, routine_id, today, "skipped", 0)
            disc = await self.db.get_discipline(uid)
            await self.db.update_discipline(
                uid,
                total_skipped=disc["total_skipped"] + 1,
            )
        elif status == "delayed":
            await self.db.log_task(uid, routine_id, today, "delayed", 0)
            disc = await self.db.get_discipline(uid)
            await self.db.update_discipline(
                uid,
                total_delayed=disc["total_delayed"] + 1,
            )

        await self.update_discipline_score(uid)
        disc = await self.db.get_discipline(uid)
        return {"xp": xp, "streak": disc["streak"], "level": disc["level"], "score": disc["discipline_score"]}

    async def get_level(self, uid: int) -> int:
        disc = await self.db.get_discipline(uid)
        return disc["level"]

    async def get_streak(self, uid: int) -> int:
        disc = await self.db.get_discipline(uid)
        return disc["streak"]

    async def get_xp(self, uid: int) -> int:
        disc = await self.db.get_discipline(uid)
        return disc["xp"]

    async def get_discipline_score(self, uid: int) -> int:
        disc = await self.db.get_discipline(uid)
        return disc["discipline_score"]

    async def create_routines_from_goals(self, uid: int, routine_slots: list[dict], saved_goals: list[dict]) -> int:
        old = await self.db.get_routines(uid)
        for r in old:
            await self.db.delete_routine(r["id"])

        goal_map = {}
        for g in saved_goals:
            goal_map[g["name"].lower().replace(" ", "_")] = g["id"]

        created = 0
        for slot in routine_slots:
            time_str = slot["time"]
            title = slot["title"]
            goal_key = slot.get("goal_key", "")

            if not title:
                continue

            goal_id = 0
            gk_lower = goal_key.lower().strip() if goal_key else ""
            if gk_lower in goal_map:
                goal_id = goal_map[gk_lower]
            else:
                for gname, gid in goal_map.items():
                    if gname == gk_lower or gk_lower in gname:
                        goal_id = gid
                        break

            await self.db.add_routine(
                uid=uid,
                title=title[:100],
                scheduled_time=time_str,
                goal_id=goal_id,
                description=title[:200],
                category=goal_key or "general",
                duration=45,
                difficulty="medium",
                day_of_week="daily",
            )
            created += 1

        return created

    async def create_routines_from_schedule(self, uid: int, schedule_data: dict):
        return 0

    async def get_tasks_for_time(self, current_hour: int, current_minute: int):
        time_str = f"{current_hour:02d}:{current_minute:02d}"
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%A").lower()
        return await self.db.fetchall(
            "SELECT r.*, u.language FROM routines r JOIN users u ON u.user_id = r.user_id WHERE r.active = 1 AND r.scheduled_time = ? AND (r.day_of_week = 'daily' OR r.day_of_week = ?) ORDER BY r.user_id",
            (time_str, today),
        )

    def build_reminder_text(self, routine: dict, lang: str) -> str:
        labels = {
            "uz": {
                "title": f"🧠 *{routine['title']} Vaqti!*",
                "time": f"⏰ {routine['scheduled_time']}",
                "desc": f"🎯 {routine['description']}" if routine.get("description") else "",
                "duration": f"⏳ Davomiyligi: {routine['duration_minutes']} daqiqa",
                "prompt": "Bugungi vazifani bajardingizmi?",
            },
            "ru": {
                "title": f"🧠 *Время {routine['title']}!*",
                "time": f"⏰ {routine['scheduled_time']}",
                "desc": f"🎯 {routine['description']}" if routine.get("description") else "",
                "duration": f"⏳ Длительность: {routine['duration_minutes']} мин",
                "prompt": "Вы выполнили сегодняшнюю задачу?",
            },
            "en": {
                "title": f"🧠 *{routine['title']} Time!*",
                "time": f"⏰ {routine['scheduled_time']}",
                "desc": f"🎯 {routine['description']}" if routine.get("description") else "",
                "duration": f"⏳ Duration: {routine['duration_minutes']} min",
                "prompt": "Did you complete today's task?",
            },
        }
        lbl = labels.get(lang, labels["en"])
        parts = [lbl["title"], "", lbl["time"]]
        if lbl["desc"]:
            parts.append(lbl["desc"])
        parts.append(lbl["duration"])
        parts.append("")
        parts.append(lbl["prompt"])
        return "\n".join(parts)

    def build_motivation_text(self, result: dict, status: str, lang: str) -> str:
        labels = {
            "uz": {
                "completed": "🔥 Ajoyib ish!",
                "partial": "🟡 Yaxshi! Qisman bajarildi.",
                "skipped": "❌ Vazifa o'tkazib yuborildi.",
                "xp": f"+{result['xp']} XP qo'lga kiritdingiz.",
                "streak": f"📈 Joriy streak: {result['streak']} kun",
                "level": f"⭐ Daraja: {result['level']}",
                "score": f"🎯 Intizom ball: {result['score']}/100",
                "skip_msg": "Ertaga davom eting! Kichik qadamlar ham muhim.",
                "partial_msg": "Qisman bajarildi — baribir rivojlanish!",
            },
            "ru": {
                "completed": "🔥 Отличная работа!",
                "partial": "🟡 Хорошо! Частично выполнено.",
                "skipped": "❌ Задача пропущена.",
                "xp": f"+{result['xp']} XP получено.",
                "streak": f"📈 Текущая серия: {result['streak']} дн.",
                "level": f"⭐ Уровень: {result['level']}",
                "score": f"🎯 Балл дисциплины: {result['score']}/100",
                "skip_msg": "Продолжайте завтра! Даже маленькие шаги важны.",
                "partial_msg": "Частично выполнено — всё равно прогресс!",
            },
            "en": {
                "completed": "🔥 Great work!",
                "partial": "🟡 Good! Partially completed.",
                "skipped": "❌ Task skipped.",
                "xp": f"+{result['xp']} XP earned.",
                "streak": f"📈 Current streak: {result['streak']} days",
                "level": f"⭐ Level: {result['level']}",
                "score": f"🎯 Discipline score: {result['score']}/100",
                "skip_msg": "Continue tomorrow! Even small steps matter.",
                "partial_msg": "Partially done — still progress!",
            },
        }
        lbl = labels.get(lang, labels["en"])
        if status == "completed":
            lines = [lbl["completed"], "", lbl["xp"], lbl["streak"], lbl["level"], lbl["score"]]
        elif status == "partial":
            lines = [lbl["partial"], "", lbl["xp"], lbl["streak"], lbl["partial_msg"]]
        elif status == "skipped":
            lines = [lbl["skipped"], "", lbl["skip_msg"], lbl["streak"]]
        else:
            lines = [lbl["completed"], "", lbl["xp"], lbl["streak"]]
        return "\n".join(lines)
