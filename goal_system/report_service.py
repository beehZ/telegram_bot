import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("report_service")

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


async def build_daily_report(db, uid: int, lang: str = "uz") -> str:
    today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
    routines = await db.get_todays_routines(uid)
    logs = await db.get_task_logs(uid, today)
    disc = await db.get_discipline(uid)

    log_map = {l["routine_id"]: l for l in logs}
    completed = []
    partial = []
    skipped = []
    pending = []

    for r in routines:
        l = log_map.get(r["id"])
        if l is None or l["status"] == "pending":
            pending.append(r)
        elif l["status"] == "completed":
            completed.append(r)
        elif l["status"] == "partial":
            partial.append(r)
        elif l["status"] == "skipped":
            skipped.append(r)

    total = len(routines)
    done_count = len(completed) + len(partial)
    pct = round(done_count / total * 100) if total else 0

    labels = {
        "uz": {
            "title": "📊 *Bugungi Hisobot*",
            "completed": "✅ Bajarildi",
            "partial": "🟡 Qisman",
            "skipped": "❌ O'tkazib yuborildi",
            "pending": "⬜ Kutilmoqda",
            "rate": f"Bajarish darajasi: {pct}%",
            "streak": f"🔥 Streak: {disc['streak']} kun",
            "xp": f"⭐ XP: {disc['xp']} (Daraja {disc['level']})",
            "score": f"🎯 Intizom ball: {disc['discipline_score']}/100",
            "none": "Bugun uchun vazifalar yo'q.",
        },
        "ru": {
            "title": "📊 *Отчет за сегодня*",
            "completed": "✅ Выполнено",
            "partial": "🟡 Частично",
            "skipped": "❌ Пропущено",
            "pending": "⬜ Ожидает",
            "rate": f"Уровень выполнения: {pct}%",
            "streak": f"🔥 Серия: {disc['streak']} дн.",
            "xp": f"⭐ XP: {disc['xp']} (Уровень {disc['level']})",
            "score": f"🎯 Балл дисциплины: {disc['discipline_score']}/100",
            "none": "На сегодня задач нет.",
        },
        "en": {
            "title": "📊 *Today's Report*",
            "completed": "✅ Completed",
            "partial": "🟡 Partial",
            "skipped": "❌ Skipped",
            "pending": "⬜ Pending",
            "rate": f"Completion Rate: {pct}%",
            "streak": f"🔥 Streak: {disc['streak']} days",
            "xp": f"⭐ XP: {disc['xp']} (Level {disc['level']})",
            "score": f"🎯 Discipline Score: {disc['discipline_score']}/100",
            "none": "No tasks scheduled for today.",
        },
    }
    lbl = labels.get(lang, labels["en"])

    lines = [lbl["title"], ""]

    if not routines:
        lines.append(lbl["none"])
        lines.append("")
        lines.append(lbl["streak"])
        lines.append(lbl["xp"])
        lines.append(lbl["score"])
        return "\n".join(lines)

    for r in completed:
        lines.append(f"{lbl['completed']} — {r['title']} ({r['scheduled_time']})")
    for r in partial:
        log = log_map.get(r["id"], {})
        xp = log.get("xp_earned", 0) if log else 0
        lines.append(f"{lbl['partial']} — {r['title']} (+{xp} XP)")
    for r in skipped:
        lines.append(f"{lbl['skipped']} — {r['title']}")
    for r in pending:
        lines.append(f"{lbl['pending']} — {r['title']} ({r['scheduled_time']})")

    lines.append("")
    lines.append(lbl["rate"])
    lines.append(lbl["streak"])
    lines.append(lbl["xp"])
    lines.append(lbl["score"])

    return "\n".join(lines)


async def build_weekly_report(db, uid: int, lang: str = "uz") -> str:
    today = date.today()
    week_ago = today - timedelta(days=6)
    logs = await db.get_task_logs_range(uid, week_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    disc = await db.get_discipline(uid)

    day_map: dict[str, dict] = {}
    for log in logs:
        d = log["date"]
        if d not in day_map:
            day_map[d] = {"completed": 0, "partial": 0, "skipped": 0, "total": 0}
        day_map[d]["total"] += 1
        if log["status"] in ("completed",):
            day_map[d]["completed"] += 1
        elif log["status"] == "partial":
            day_map[d]["partial"] += 1
        elif log["status"] == "skipped":
            day_map[d]["skipped"] += 1

    best_day = max(day_map.items(), key=lambda kv: kv[1]["completed"]) if day_map else ("-", {})

    completed = sum(1 for l in logs if l["status"] in ("completed", "partial"))
    skipped = sum(1 for l in logs if l["status"] == "skipped")
    total = len(logs)
    pct = round(completed / total * 100) if total else 0

    category_data: dict[str, int] = {}
    for log in logs:
        cat = log.get("category", "general")
        if log["status"] in ("completed", "partial"):
            category_data[cat] = category_data.get(cat, 0) + 1

    most_skipped_cat = max(category_data, key=category_data.get) if category_data else "-"

    labels = {
        "uz": {
            "title": "📅 *Haftalik Hisobot*",
            "completed": f"✅ Bajarilgan: {completed}/{total} ({pct}%)",
            "streak": f"🔥 Streak: {disc['streak']} kun",
            "xp": f"⭐ XP: {disc['xp']} (Daraja {disc['level']})",
            "score": f"🎯 Intizom ball: {disc['discipline_score']}/100",
            "best": f"🏆 Eng yaxshi kun: {best_day[0]} ({best_day[1]['completed']} ta)",
            "best_cat": f"📊 Eng ko'p bajarilgan: {most_skipped_cat}",
            "none": "Bu hafta hech qanday vazifa qayd etilmagan.",
        },
        "ru": {
            "title": "📅 *Еженедельный Отчет*",
            "completed": f"✅ Выполнено: {completed}/{total} ({pct}%)",
            "streak": f"🔥 Серия: {disc['streak']} дн.",
            "xp": f"⭐ XP: {disc['xp']} (Уровень {disc['level']})",
            "score": f"🎯 Балл дисциплины: {disc['discipline_score']}/100",
            "best": f"🏆 Лучший день: {best_day[0]} ({best_day[1]['completed']} шт.)",
            "best_cat": f"📊 Самая продуктивная: {most_skipped_cat}",
            "none": "На этой неделе задачи не записаны.",
        },
        "en": {
            "title": "📅 *Weekly Report*",
            "completed": f"✅ Completed: {completed}/{total} ({pct}%)",
            "streak": f"🔥 Streak: {disc['streak']} days",
            "xp": f"⭐ XP: {disc['xp']} (Level {disc['level']})",
            "score": f"🎯 Discipline Score: {disc['discipline_score']}/100",
            "best": f"🏆 Best day: {best_day[0]} ({best_day[1]['completed']} tasks)",
            "best_cat": f"📊 Most completed category: {most_skipped_cat}",
            "none": "No tasks logged this week.",
        },
    }
    lbl = labels.get(lang, labels["en"])

    lines = [lbl["title"], "", lbl["completed"], lbl["streak"], lbl["xp"], lbl["score"], ""]
    if total:
        lines.append(lbl["best"])
        lines.append(lbl["best_cat"])
    else:
        lines.append(lbl["none"])

    return "\n".join(lines)
