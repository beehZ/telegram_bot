import aiosqlite
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "life.db"

CREATE_REMINDERS = """
CREATE TABLE IF NOT EXISTS life_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    time TEXT NOT NULL,
    repeat INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    custom_text TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
)
"""

CREATE_CHECKINS = """
CREATE TABLE IF NOT EXISTS life_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    mood TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now'))
)
"""

CREATE_CHECKIN_STREAKS = """
CREATE TABLE IF NOT EXISTS life_checkin_streaks (
    user_id INTEGER PRIMARY KEY,
    streak INTEGER DEFAULT 0,
    last_date TEXT
)
"""

CREATE_EXAMS = """
CREATE TABLE IF NOT EXISTS life_exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    exam_date TEXT NOT NULL,
    notified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
)
"""

CREATE_STUDY_LOGS = """
CREATE TABLE IF NOT EXISTS life_study_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    hours REAL NOT NULL,
    timestamp TEXT DEFAULT (datetime('now'))
)
"""

CREATE_HOMEWORK = """
CREATE TABLE IF NOT EXISTS life_homework (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
)
"""

CREATE_FOCUS_SESSIONS = """
CREATE TABLE IF NOT EXISTS life_focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    duration_minutes INTEGER DEFAULT 25,
    completed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
)
"""

CREATE_STUDY_STREAKS = """
CREATE TABLE IF NOT EXISTS life_study_streaks (
    user_id INTEGER PRIMARY KEY,
    streak INTEGER DEFAULT 0,
    last_date TEXT
)
"""

ALL_TABLES = [
    CREATE_REMINDERS, CREATE_CHECKINS, CREATE_CHECKIN_STREAKS,
    CREATE_EXAMS, CREATE_STUDY_LOGS, CREATE_HOMEWORK,
    CREATE_FOCUS_SESSIONS, CREATE_STUDY_STREAKS,
]


class LifeDB:
    def __init__(self):
        self.path = str(DB_PATH)

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            for sql in ALL_TABLES:
                await db.execute(sql)
            await db.commit()

    async def execute(self, sql: str, params=()):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(sql, params)
            await db.commit()
            return cur.lastrowid

    async def fetchone(self, sql: str, params=()):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            cur = await db.execute(sql, params)
            return await cur.fetchone()

    async def fetchall(self, sql: str, params=()):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            cur = await db.execute(sql, params)
            return await cur.fetchall()

    # ── Reminders ──

    async def add_reminder(self, user_id: int, rtype: str, time: str, repeat: int = 1, custom_text: str = ""):
        return await self.execute(
            "INSERT INTO life_reminders (user_id, type, time, repeat, custom_text) VALUES (?, ?, ?, ?, ?)",
            (user_id, rtype, time, repeat, custom_text),
        )

    async def get_reminders(self, user_id: int, active_only: bool = True):
        if active_only:
            return await self.fetchall("SELECT * FROM life_reminders WHERE user_id = ? AND active = 1 ORDER BY time", (user_id,))
        return await self.fetchall("SELECT * FROM life_reminders WHERE user_id = ? ORDER BY time", (user_id,))

    async def get_all_active_reminders(self):
        return await self.fetchall("SELECT * FROM life_reminders WHERE active = 1")

    async def delete_reminder(self, reminder_id: int):
        await self.execute("DELETE FROM life_reminders WHERE id = ?", (reminder_id,))

    async def toggle_reminder(self, reminder_id: int, active: int):
        await self.execute("UPDATE life_reminders SET active = ? WHERE id = ?", (active, reminder_id))

    # ── Check-ins ──

    async def add_checkin(self, user_id: int, date: str, mood: str):
        return await self.execute(
            "INSERT INTO life_checkins (user_id, date, mood) VALUES (?, ?, ?)",
            (user_id, date, mood),
        )

    async def get_checkins(self, user_id: int, limit: int = 30):
        return await self.fetchall(
            "SELECT * FROM life_checkins WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

    async def get_checkin_streak(self, user_id: int):
        row = await self.fetchone("SELECT * FROM life_checkin_streaks WHERE user_id = ?", (user_id,))
        if row:
            return {"streak": row["streak"], "last_date": row["last_date"]}
        return {"streak": 0, "last_date": None}

    async def update_checkin_streak(self, user_id: int, streak: int, last_date: str):
        await self.execute(
            "INSERT OR REPLACE INTO life_checkin_streaks (user_id, streak, last_date) VALUES (?, ?, ?)",
            (user_id, streak, last_date),
        )

    async def reset_checkin_streak(self, user_id: int):
        await self.execute(
            "INSERT OR REPLACE INTO life_checkin_streaks (user_id, streak, last_date) VALUES (?, 0, NULL)",
            (user_id,),
        )

    async def get_today_checkin(self, user_id: int, date: str):
        return await self.fetchone(
            "SELECT * FROM life_checkins WHERE user_id = ? AND date = ?",
            (user_id, date),
        )

    # ── Exams ──

    async def add_exam(self, user_id: int, subject: str, exam_date: str):
        return await self.execute(
            "INSERT INTO life_exams (user_id, subject, exam_date) VALUES (?, ?, ?)",
            (user_id, subject, exam_date),
        )

    async def get_exams(self, user_id: int):
        return await self.fetchall(
            "SELECT * FROM life_exams WHERE user_id = ? ORDER BY exam_date",
            (user_id,),
        )

    async def delete_exam(self, exam_id: int):
        await self.execute("DELETE FROM life_exams WHERE id = ?", (exam_id,))

    async def get_upcoming_exams(self):
        return await self.fetchall(
            "SELECT * FROM life_exams WHERE notified = 0 AND exam_date >= date('now') ORDER BY exam_date"
        )

    async def mark_exam_notified(self, exam_id: int):
        await self.execute("UPDATE life_exams SET notified = 1 WHERE id = ?", (exam_id,))

    # ── Study Logs ──

    async def log_study(self, user_id: int, date: str, hours: float):
        return await self.execute(
            "INSERT INTO life_study_logs (user_id, date, hours) VALUES (?, ?, ?)",
            (user_id, date, hours),
        )

    async def get_study_logs(self, user_id: int, limit: int = 30):
        return await self.fetchall(
            "SELECT * FROM life_study_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

    async def get_today_study(self, user_id: int, date: str):
        row = await self.fetchone(
            "SELECT SUM(hours) as total FROM life_study_logs WHERE user_id = ? AND date = ?",
            (user_id, date),
        )
        return row["total"] if row and row["total"] else 0

    async def get_study_streak(self, user_id: int):
        row = await self.fetchone("SELECT * FROM life_study_streaks WHERE user_id = ?", (user_id,))
        if row:
            return {"streak": row["streak"], "last_date": row["last_date"]}
        return {"streak": 0, "last_date": None}

    async def update_study_streak(self, user_id: int, streak: int, last_date: str):
        await self.execute(
            "INSERT OR REPLACE INTO life_study_streaks (user_id, streak, last_date) VALUES (?, ?, ?)",
            (user_id, streak, last_date),
        )

    # ── Homework ──

    async def add_homework(self, user_id: int, task: str, date: str):
        return await self.execute(
            "INSERT INTO life_homework (user_id, task, date) VALUES (?, ?, ?)",
            (user_id, task, date),
        )

    async def get_homework(self, user_id: int, date: Optional[str] = None):
        if date:
            return await self.fetchall(
                "SELECT * FROM life_homework WHERE user_id = ? AND date = ? ORDER BY id",
                (user_id, date),
            )
        return await self.fetchall(
            "SELECT * FROM life_homework WHERE user_id = ? ORDER BY date DESC, id",
            (user_id,),
        )

    async def complete_homework(self, homework_id: int):
        await self.execute("UPDATE life_homework SET completed = 1 WHERE id = ?", (homework_id,))

    async def delete_homework(self, homework_id: int):
        await self.execute("DELETE FROM life_homework WHERE id = ?", (homework_id,))

    # ── Focus Sessions ──

    async def start_focus(self, user_id: int, start_time: str, duration: int = 25):
        return await self.execute(
            "INSERT INTO life_focus_sessions (user_id, start_time, duration_minutes) VALUES (?, ?, ?)",
            (user_id, start_time, duration),
        )

    async def complete_focus(self, session_id: int):
        await self.execute("UPDATE life_focus_sessions SET completed = 1 WHERE id = ?", (session_id,))

    async def get_active_focus(self, user_id: int):
        return await self.fetchone(
            "SELECT * FROM life_focus_sessions WHERE user_id = ? AND completed = 0 ORDER BY id DESC LIMIT 1",
            (user_id,),
        )

    async def get_today_focus_count(self, user_id: int, date: str):
        row = await self.fetchone(
            "SELECT COUNT(*) as cnt FROM life_focus_sessions WHERE user_id = ? AND date(start_time) = ? AND completed = 1",
            (user_id, date),
        )
        return row["cnt"] if row else 0
