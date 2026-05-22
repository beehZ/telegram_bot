from datetime import datetime, date
from zoneinfo import ZoneInfo

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


class ProgressTracker:
    def __init__(self, db):
        self.db = db

    async def check_in(self, uid: int, goal_id: int):
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        existing = await self.db.fetchone(
            "SELECT id FROM progress WHERE user_id = ? AND goal_id = ? AND date = ?",
            (uid, goal_id, today),
        )
        if not existing:
            await self.db.log_progress(uid, goal_id, True, today)
        await self._update_streak(uid, goal_id)

    async def _update_streak(self, uid: int, goal_id: int):
        streak = await self.db.get_streak(uid, goal_id)
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        yesterday_str = today.strftime("%Y-%m-%d")  # will adjust

        from datetime import timedelta
        yesterday = today - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")

        if streak:
            last = streak.get("last_date", "")
            current = streak.get("current_streak", 0)
            longest = streak.get("longest_streak", 0)

            if last == yesterday_str:
                current += 1
            elif last == today_str:
                current = current
            else:
                current = 1

            longest = max(longest, current)
            await self.db.update_streak(uid, goal_id, current, longest, today_str)
        else:
            await self.db.update_streak(uid, goal_id, 1, 1, today_str)

    async def get_weekly_report(self, uid: int, lang: str = "uz") -> str:
        summary = await self.db.get_weekly_summary(uid)
        goals_data = summary.get("goals", [])
        if not goals_data:
            msgs = {"uz": "Hali hech qanday maqsad qo'ymagansiz. /goal orqali maqsad qo'shing!", "ru": "Вы еще не поставили ни одной цели. Добавьте цель через /goal", "en": "You haven't set any goals yet. Add a goal with /goal"}
            return msgs.get(lang, msgs["uz"])

        labels = {
            "uz": {"title": "📊 *Haftalik Hisobot*", "done": "martta bajarildi", "total": "📈 Umumiy: {}/{} maqsad bajarildi ({}%)", "streak": "🔥 *{}*: {}-kunlik streak!"},
            "ru": {"title": "📊 *Еженедельный Отчет*", "done": "раз выполнено", "total": "📈 Итого: {}/{} целей выполнено ({}%)", "streak": "🔥 *{}*: streak {} дней!"},
            "en": {"title": "📊 *Weekly Report*", "done": "times completed", "total": "📈 Total: {}/{} goals completed ({}%)", "streak": "🔥 *{}*: {}-day streak!"},
        }
        lbl = labels.get(lang, labels["uz"])

        lines = [lbl["title"], ""]
        total_goals = len(goals_data)
        completed_count = 0

        for g in goals_data:
            name = g.get("name", "?")
            cat = g.get("category", "?")
            done = g.get("done", 0)
            has_prog = g.get("has_progress", 0)
            status = "✅" if has_prog else "❌"
            if has_prog:
                completed_count += 1
            lines.append(f"{status} *{name}* ({cat}) — {done} {lbl['done']}")

        lines.append("")
        pct = round(completed_count / total_goals * 100) if total_goals else 0
        lines.append(lbl["total"].format(completed_count, total_goals, pct))

        for g in goals_data:
            goal_name = g.get("name", "?")
            gid = g.get("id")
            if gid:
                s = await self.db.get_streak(uid, gid)
                if s and s.get("current_streak", 0) > 0:
                    lines.append(lbl["streak"].format(goal_name, s["current_streak"]))

        return "\n".join(lines)

    async def format_streak_message(self, uid: int, lang: str = "uz") -> str:
        goals = await self.db.get_goals(uid)
        parts = []
        for g in goals:
            s = await self.db.get_streak(uid, g["id"])
            if s and s.get("current_streak", 0) > 0:
                msgs = {"uz": f"• {g['name']}: {s['current_streak']} kun 🔥", "ru": f"• {g['name']}: {s['current_streak']} дн. 🔥", "en": f"• {g['name']}: {s['current_streak']} days 🔥"}
                parts.append(msgs.get(lang, msgs["uz"]))
        if not parts:
            none_msgs = {"uz": "Hozircha streaklar mavjud emas. Bugun maqsadlaringizni boshlang!", "ru": "Пока нет серий. Начните сегодня!", "en": "No streaks yet. Start your goals today!"}
            return none_msgs.get(lang, none_msgs["uz"])
        titles = {"uz": "🏆 *Sizning streak-laringiz:*", "ru": "🏆 *Ваши серии:*", "en": "🏆 *Your Streaks:*"}
        return titles.get(lang, titles["uz"]) + "\n" + "\n".join(parts)
