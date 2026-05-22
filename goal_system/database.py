import logging
import sqlite3
import aiosqlite
from pathlib import Path

logger = logging.getLogger("db.migrations")
DB_PATH = Path(__file__).parent.parent / "goals.db"


class Database:
    def __init__(self):
        self.path = str(DB_PATH)

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(CREATE_SQL)
            await db.commit()
        await self.run_migrations()

    async def ensure_column(self, table: str, column: str, definition: str):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            cur = await db.execute(f"PRAGMA table_info({table})")
            rows = await cur.fetchall()
            existing_cols = {r["name"] for r in rows}
        if column not in existing_cols:
            await self.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
            logger.info("Added missing column: %s.%s", table, column)

    async def ensure_table(self, create_sql: str):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(create_sql)
            await db.commit()

    async def run_migrations(self):
        logger.info("Running database schema migrations...")

        await self.ensure_column("users", "current_balance", "current_balance REAL DEFAULT 0")
        await self.ensure_column("users", "total_income", "total_income REAL DEFAULT 0")
        await self.ensure_column("users", "total_expense", "total_expense REAL DEFAULT 0")
        await self.ensure_column("users", "updated_at", "updated_at TEXT")
        await self.ensure_column("routines", "day_of_week", "day_of_week TEXT DEFAULT 'daily'")

        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS transactions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              amount REAL NOT NULL,
              tx_type TEXT NOT NULL CHECK(tx_type IN ('income','expense')),
              category TEXT NOT NULL DEFAULT 'other',
              description TEXT DEFAULT '',
              date TEXT NOT NULL,
              created_at TEXT DEFAULT (datetime('now', 'localtime')),
              FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS daily_finance (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              date TEXT NOT NULL,
              total_income REAL DEFAULT 0,
              total_expense REAL DEFAULT 0,
              transaction_count INTEGER DEFAULT 0,
              created_at TEXT DEFAULT (datetime('now', 'localtime')),
              FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)

        await self.ensure_index("idx_transactions_user_date", "transactions", "user_id, date DESC")
        await self.ensure_index("idx_daily_finance_user_date", "daily_finance", "user_id, date")

        # ── Discipline System Tables ──
        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS routines (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              goal_id INTEGER DEFAULT 0,
              title TEXT NOT NULL,
              description TEXT DEFAULT '',
              category TEXT DEFAULT 'general',
              scheduled_time TEXT NOT NULL,
              duration_minutes INTEGER DEFAULT 30,
              difficulty TEXT DEFAULT 'medium',
              repeat_type TEXT DEFAULT 'daily',
              day_of_week TEXT DEFAULT 'daily',
              active INTEGER DEFAULT 1,
              created_at TEXT DEFAULT (datetime('now', 'localtime')),
              FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS task_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              routine_id INTEGER,
              date TEXT NOT NULL,
              status TEXT DEFAULT 'pending',
              completed_at TEXT,
              xp_earned INTEGER DEFAULT 0,
              created_at TEXT DEFAULT (datetime('now', 'localtime')),
              FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS disciplines (
              user_id INTEGER PRIMARY KEY,
              xp INTEGER DEFAULT 0,
              level INTEGER DEFAULT 1,
              discipline_score INTEGER DEFAULT 50,
              streak INTEGER DEFAULT 0,
              longest_streak INTEGER DEFAULT 0,
              last_active_date TEXT,
              total_completed INTEGER DEFAULT 0,
              total_skipped INTEGER DEFAULT 0,
              total_delayed INTEGER DEFAULT 0,
              updated_at TEXT DEFAULT (datetime('now', 'localtime')),
              FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        await self.ensure_index("idx_routines_user", "routines", "user_id, active")
        await self.ensure_index("idx_task_logs_user_date", "task_logs", "user_id, date")

        # ── Manual Task Activation Tables ──
        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS active_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL UNIQUE,
              routine_id INTEGER NOT NULL,
              status TEXT DEFAULT 'active',
              started_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              paused_at TEXT,
              total_pause_seconds INTEGER DEFAULT 0,
              focus_mode INTEGER DEFAULT 0,
              focus_minutes INTEGER DEFAULT 25,
              created_at TEXT DEFAULT (datetime('now', 'localtime')),
              FOREIGN KEY (user_id) REFERENCES users(user_id),
              FOREIGN KEY (routine_id) REFERENCES routines(id)
            );
        """)
        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS pause_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              routine_id INTEGER NOT NULL,
              session_id INTEGER NOT NULL,
              paused_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              resumed_at TEXT,
              pause_seconds INTEGER DEFAULT 0,
              FOREIGN KEY (user_id) REFERENCES users(user_id),
              FOREIGN KEY (routine_id) REFERENCES routines(id)
            );
        """)
        await self.ensure_table("""
            CREATE TABLE IF NOT EXISTS focus_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              routine_id INTEGER NOT NULL,
              session_id INTEGER,
              focus_type TEXT DEFAULT 'pomodoro',
              planned_minutes INTEGER DEFAULT 25,
              actual_minutes INTEGER DEFAULT 0,
              completed INTEGER DEFAULT 0,
              started_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              completed_at TEXT,
              FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        await self.ensure_index("idx_active_sessions_user", "active_sessions", "user_id")
        await self.ensure_index("idx_pause_logs_session", "pause_logs", "session_id")
        await self.ensure_index("idx_focus_sessions_user", "focus_sessions", "user_id")
        logger.info("Database migrations complete.")

    async def ensure_index(self, name: str, table: str, columns: str):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            cur = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (name,))
            row = await cur.fetchone()
        if not row:
            await self.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
            logger.info("Created index: %s on %s (%s)", name, table, columns)

    async def execute(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(sql, params)
            await db.commit()
            return cur

    async def fetchone(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            cur = await db.execute(sql, params)
            row = await cur.fetchone()
            return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_user(self, uid: int):
        return await self.fetchone("SELECT * FROM users WHERE user_id = ?", (uid,))

    async def ensure_user(self, uid: int, tz: str = "Asia/Tashkent", lang: str = "uz"):
        u = await self.get_user(uid)
        if not u:
            await self.execute(
                "INSERT INTO users (user_id, timezone, language) VALUES (?, ?, ?)", (uid, tz, lang)
            )
        else:
            if "language" not in u:
                await self.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'uz'")
                await self.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, uid))

    async def get_language(self, uid: int) -> str:
        u = await self.get_user(uid)
        if u and u.get("language"):
            return u["language"]
        return "uz"

    async def set_language(self, uid: int, lang: str):
        await self.ensure_user(uid)
        await self.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, uid))

    async def add_goal(self, uid: int, name: str, category: str, priority: int = 1) -> int:
        existing = await self.fetchone(
            "SELECT id FROM goals WHERE user_id = ? AND name = ? AND status = 'active'",
            (uid, name),
        )
        if existing:
            return existing["id"]
        cur = await self.execute(
            "INSERT INTO goals (user_id, name, category, priority) VALUES (?, ?, ?, ?)",
            (uid, name, category, priority),
        )
        return cur.lastrowid

    async def get_goals(self, uid: int, status: str = "active"):
        return await self.fetchall(
            "SELECT * FROM goals WHERE user_id = ? AND status = ? ORDER BY priority",
            (uid, status),
        )

    async def save_goal_detail(self, uid: int, goal_id: int, key: str, value: str):
        await self.execute(
            "INSERT INTO goal_details (user_id, goal_id, key, value) VALUES (?, ?, ?, ?)",
            (uid, goal_id, key, value),
        )

    async def get_goal_details(self, goal_id: int):
        return await self.fetchall(
            "SELECT * FROM goal_details WHERE goal_id = ?", (goal_id,)
        )

    async def get_all_goal_details(self, uid: int):
        return await self.fetchall(
            "SELECT gd.* FROM goal_details gd JOIN goals g ON g.id = gd.goal_id WHERE g.user_id = ?",
            (uid,),
        )

    async def save_schedule(self, uid: int, goal_id: int, day: int, start: str, end: str, activity: str):
        await self.execute(
            "INSERT INTO schedules (user_id, goal_id, day_of_week, start_time, end_time, activity) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, goal_id, day, start, end, activity),
        )

    async def get_schedules(self, uid: int):
        return await self.fetchall(
            "SELECT s.*, g.name as goal_name, g.category FROM schedules s JOIN goals g ON g.id = s.goal_id WHERE s.user_id = ? ORDER BY s.day_of_week, s.start_time",
            (uid,),
        )

    async def clear_schedules(self, uid: int):
        await self.execute("DELETE FROM schedules WHERE user_id = ?", (uid,))
        await self.execute("DELETE FROM reminders WHERE user_id = ?", (uid,))

    async def save_reminder(self, uid: int, goal_id: int, msg: str, time: str, dow: int, job_id: str = ""):
        cur = await self.execute(
            "INSERT INTO reminders (user_id, goal_id, message, remind_time, day_of_week, job_id) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, goal_id, msg, time, dow, job_id),
        )
        return cur.lastrowid

    async def get_reminders(self, uid: int):
        return await self.fetchall(
            "SELECT r.*, g.name as goal_name FROM reminders r JOIN goals g ON g.id = r.goal_id WHERE r.user_id = ? AND r.active = 1",
            (uid,),
        )

    async def update_reminder_job_id(self, rid: int, job_id: str):
        await self.execute("UPDATE reminders SET job_id = ? WHERE id = ?", (job_id, rid))

    async def log_progress(self, uid: int, goal_id: int, completed: bool, date: str, notes: str = ""):
        await self.execute(
            "INSERT INTO progress (user_id, goal_id, date, completed, notes) VALUES (?, ?, ?, ?, ?)",
            (uid, goal_id, int(completed), date, notes),
        )

    async def get_progress(self, uid: int, goal_id: int, limit: int = 30):
        return await self.fetchall(
            "SELECT * FROM progress WHERE user_id = ? AND goal_id = ? ORDER BY date DESC LIMIT ?",
            (uid, goal_id, limit),
        )

    async def get_streak(self, uid: int, goal_id: int):
        return await self.fetchone(
            "SELECT * FROM streaks WHERE user_id = ? AND goal_id = ?", (uid, goal_id)
        )

    async def update_streak(self, uid: int, goal_id: int, current: int, longest: int, last_date: str):
        s = await self.get_streak(uid, goal_id)
        if s:
            await self.execute(
                "UPDATE streaks SET current_streak = ?, longest_streak = ?, last_date = ? WHERE user_id = ? AND goal_id = ?",
                (current, longest, last_date, uid, goal_id),
            )
        else:
            await self.execute(
                "INSERT INTO streaks (user_id, goal_id, current_streak, longest_streak, last_date) VALUES (?, ?, ?, ?, ?)",
                (uid, goal_id, current, longest, last_date),
            )

    async def save_nutrition_goal(self, uid: int, goal_id: int, cal: int, protein: float, fat: float, carbs: float, water: int):
        existing = await self.fetchone(
            "SELECT id FROM nutrition_goals WHERE user_id = ? AND goal_id = ?", (uid, goal_id)
        )
        if existing:
            await self.execute(
                "UPDATE nutrition_goals SET daily_calories = ?, protein_grams = ?, fat_grams = ?, carb_grams = ?, water_ml = ? WHERE id = ?",
                (cal, protein, fat, carbs, water, existing["id"]),
            )
        else:
            await self.execute(
                "INSERT INTO nutrition_goals (user_id, goal_id, daily_calories, protein_grams, fat_grams, carb_grams, water_ml) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, goal_id, cal, protein, fat, carbs, water),
            )

    async def get_nutrition_goal(self, uid: int):
        return await self.fetchone(
            "SELECT * FROM nutrition_goals WHERE user_id = ? ORDER BY id DESC LIMIT 1", (uid,)
        )

    async def get_weekly_summary(self, uid: int) -> dict:
        rows = await self.fetchall(
            """SELECT g.id, g.name, g.category, COUNT(p.id) as done,
               CASE WHEN g.id IN (SELECT goal_id FROM progress WHERE user_id = ? AND date >= date('now', '-7 days')) THEN 1 ELSE 0 END as has_progress
               FROM goals g LEFT JOIN progress p ON p.goal_id = g.id AND p.user_id = ? AND p.date >= date('now', '-7 days')
               WHERE g.user_id = ? AND g.status = 'active'
               GROUP BY g.id""",
            (uid, uid, uid),
        )
        seen = set()
        deduped = []
        for r in (rows or []):
            key = r.get("name", "").lower()
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        total = len(deduped)
        completed = sum(1 for r in deduped if r.get("has_progress"))
        return {"total": total, "completed": completed, "goals": deduped}

    # ── User Profile (AI Analysis) ──────────────────────────────

    async def save_user_profile(self, uid: int, profile_json: str):
        existing = await self.fetchone("SELECT id FROM user_profiles WHERE user_id = ?", (uid,))
        if existing:
            await self.execute(
                "UPDATE user_profiles SET profile_json = ?, updated_at = datetime('now', 'localtime') WHERE user_id = ?",
                (profile_json, uid),
            )
        else:
            await self.execute(
                "INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)",
                (uid, profile_json),
            )

    async def get_user_profile(self, uid: int):
        return await self.fetchone(
            "SELECT * FROM user_profiles WHERE user_id = ?", (uid,)
        )

    # ── Daily Missions ──────────────────────────────────────────

    async def save_daily_missions(self, uid: int, missions_json: str, date: str):
        existing = await self.fetchone(
            "SELECT id FROM daily_missions WHERE user_id = ? AND date = ?", (uid, date)
        )
        if existing:
            await self.execute(
                "UPDATE daily_missions SET missions_json = ? WHERE id = ?",
                (missions_json, existing["id"]),
            )
        else:
            await self.execute(
                "INSERT INTO daily_missions (user_id, date, missions_json) VALUES (?, ?, ?)",
                (uid, date, missions_json),
            )

    async def get_daily_missions(self, uid: int, date: str):
        return await self.fetchone(
            "SELECT * FROM daily_missions WHERE user_id = ? AND date = ?", (uid, date)
        )

    async def complete_mission(self, uid: int, date: str, mission_index: int):
        row = await self.get_daily_missions(uid, date)
        if not row:
            return
        import json
        missions = json.loads(row["missions_json"])
        if 0 <= mission_index < len(missions):
            missions[mission_index]["completed"] = True
            missions[mission_index]["completed_at"] = datetime.now().strftime("%H:%M")
            await self.save_daily_missions(uid, json.dumps(missions, ensure_ascii=False), date)

    async def get_mission_streak(self, uid: int) -> int:
        streak = 0
        from datetime import datetime, timedelta
        d = datetime.now()
        for _ in range(30):
            date_str = d.strftime("%Y-%m-%d")
            row = await self.get_daily_missions(uid, date_str)
            if row:
                import json
                missions = json.loads(row["missions_json"])
                if missions and any(m.get("completed") for m in missions):
                    streak += 1
                else:
                    break
            else:
                break
            d -= timedelta(days=1)
        return streak

    async def save_user_preference(self, uid: int, key: str, value: str):
        existing = await self.fetchone(
            "SELECT id FROM user_memory WHERE user_id = ? AND key = ?", (uid, key)
        )
        if existing:
            await self.execute(
                "UPDATE user_memory SET value = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (value, existing["id"]),
            )
        else:
            await self.execute(
                "INSERT INTO user_memory (user_id, key, value) VALUES (?, ?, ?)",
                (uid, key, value),
            )

    async def get_user_preference(self, uid: int, key: str):
        row = await self.fetchone(
            "SELECT value FROM user_memory WHERE user_id = ? AND key = ?", (uid, key)
        )
        return row["value"] if row else None

    async def get_all_preferences(self, uid: int):
        return await self.fetchall(
            "SELECT key, value FROM user_memory WHERE user_id = ?", (uid,)
        )


        await self.ensure_column("transactions", "raw_text", "raw_text TEXT DEFAULT ''")

        # ── Finance ────────────────────────────────────────────

    async def get_balance(self, uid: int) -> float:
        u = await self.get_user(uid)
        if u and u.get("current_balance") is not None:
            return float(u["current_balance"])
        return 0.0

    async def update_balance(self, uid: int, delta: float):
        current = await self.get_balance(uid)
        new_balance = current + delta
        await self.execute(
            "UPDATE users SET current_balance = ? WHERE user_id = ?", (new_balance, uid)
        )

    async def add_transaction(self, uid: int, amount: float, tx_type: str, category: str, description: str, date: str, raw_text: str = "") -> int:
        cur = await self.execute(
            "INSERT INTO transactions (user_id, amount, tx_type, category, description, date, raw_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, amount, tx_type, category, description, date, raw_text),
        )
        delta = amount if tx_type == "income" else -amount
        await self.update_balance(uid, delta)
        await self._upsert_daily_finance(uid, date, amount, tx_type)
        return cur.lastrowid

    async def _upsert_daily_finance(self, uid: int, date: str, amount: float, tx_type: str):
        existing = await self.fetchone(
            "SELECT id, total_income, total_expense, transaction_count FROM daily_finance WHERE user_id = ? AND date = ?",
            (uid, date),
        )
        if existing:
            new_income = existing["total_income"] + (amount if tx_type == "income" else 0)
            new_expense = existing["total_expense"] + (amount if tx_type == "expense" else 0)
            await self.execute(
                "UPDATE daily_finance SET total_income = ?, total_expense = ?, transaction_count = transaction_count + 1 WHERE id = ?",
                (new_income, new_expense, existing["id"]),
            )
        else:
            income = amount if tx_type == "income" else 0
            expense = amount if tx_type == "expense" else 0
            await self.execute(
                "INSERT INTO daily_finance (user_id, date, total_income, total_expense, transaction_count) VALUES (?, ?, ?, ?, 1)",
                (uid, date, income, expense),
            )

    async def get_transactions(self, uid: int, limit: int = 20, offset: int = 0):
        return await self.fetchall(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            (uid, limit, offset),
        )

    async def get_transactions_by_date(self, uid: int, date: str):
        return await self.fetchall(
            "SELECT * FROM transactions WHERE user_id = ? AND date = ? ORDER BY id DESC",
            (uid, date),
        )

    async def get_transactions_in_range(self, uid: int, start_date: str, end_date: str):
        return await self.fetchall(
            "SELECT * FROM transactions WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date DESC",
            (uid, start_date, end_date),
        )

    async def get_daily_finance(self, uid: int, date: str):
        return await self.fetchone(
            "SELECT * FROM daily_finance WHERE user_id = ? AND date = ?", (uid, date)
        )

    async def get_category_breakdown(self, uid: int, tx_type: str, start_date: str, end_date: str):
        return await self.fetchall(
            """SELECT category, SUM(amount) as total, COUNT(*) as count
               FROM transactions
               WHERE user_id = ? AND tx_type = ? AND date >= ? AND date <= ?
               GROUP BY category ORDER BY total DESC""",
            (uid, tx_type, start_date, end_date),
        )

    async def get_monthly_stats(self, uid: int, year: int, month: int):
        month_str = f"{year:04d}-{month:02d}%"
        return await self.fetchone(
            """SELECT COALESCE(SUM(CASE WHEN tx_type='income' THEN amount ELSE 0 END), 0) as total_income,
                      COALESCE(SUM(CASE WHEN tx_type='expense' THEN amount ELSE 0 END), 0) as total_expense,
                      COUNT(*) as tx_count
               FROM transactions
               WHERE user_id = ? AND date LIKE ?""",
            (uid, month_str),
        )

    async def check_duplicate_transaction(self, uid: int, amount: float, category: str, minutes: int = 5) -> bool:
        row = await self.fetchone(
            """SELECT id FROM transactions
               WHERE user_id = ? AND amount = ? AND category = ?
               AND datetime(created_at) >= datetime('now', ? || ' minutes', 'localtime')
               LIMIT 1""",
            (uid, amount, category, f"-{minutes}"),
        )
        return row is not None

    # ── Routines CRUD ────────────────────────────────────────

    async def add_routine(self, uid: int, title: str, scheduled_time: str,
                          goal_id: int = 0, description: str = "",
                          category: str = "general", duration: int = 30,
                          difficulty: str = "medium", repeat_type: str = "daily",
                          day_of_week: str = "daily") -> int:
        cur = await self.execute(
            "INSERT INTO routines (user_id, goal_id, title, description, category, scheduled_time, duration_minutes, difficulty, repeat_type, day_of_week) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, goal_id, title, description, category, scheduled_time, duration, difficulty, repeat_type, day_of_week),
        )
        return cur.lastrowid

    async def get_routines(self, uid: int, active_only: bool = True):
        if active_only:
            return await self.fetchall("SELECT * FROM routines WHERE user_id = ? AND active = 1 ORDER BY scheduled_time", (uid,))
        return await self.fetchall("SELECT * FROM routines WHERE user_id = ? ORDER BY scheduled_time", (uid,))

    async def get_todays_routines(self, uid: int):
        import sqlite3
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%A").lower()
        return await self.fetchall(
            "SELECT * FROM routines WHERE user_id = ? AND active = 1 AND (day_of_week = 'daily' OR day_of_week = ?) ORDER BY scheduled_time",
            (uid, today),
        )

    async def get_routine(self, rid: int):
        return await self.fetchone("SELECT * FROM routines WHERE id = ?", (rid,))

    async def update_routine_active(self, rid: int, active: int):
        await self.execute("UPDATE routines SET active = ? WHERE id = ?", (active, rid))

    async def delete_routine(self, rid: int):
        await self.execute("DELETE FROM routines WHERE id = ?", (rid,))

    async def get_all_active_routines(self):
        import sqlite3
        return await self.fetchall(
            "SELECT r.*, u.language FROM routines r JOIN users u ON u.user_id = r.user_id WHERE r.active = 1"
        )

    # ── Task Logs CRUD ───────────────────────────────────────

    async def log_task(self, uid: int, routine_id: int, date: str, status: str, xp: int = 0):
        existing = await self.fetchone(
            "SELECT id FROM task_logs WHERE user_id = ? AND routine_id = ? AND date = ?",
            (uid, routine_id, date),
        )
        if existing:
            await self.execute(
                "UPDATE task_logs SET status = ?, xp_earned = ?, completed_at = CASE WHEN ? IN ('completed','partial') THEN time('now','localtime') ELSE completed_at END WHERE id = ?",
                (status, xp, status, existing["id"]),
            )
        else:
            await self.execute(
                "INSERT INTO task_logs (user_id, routine_id, date, status, xp_earned) VALUES (?, ?, ?, ?, ?)",
                (uid, routine_id, date, status, xp),
            )

    async def get_task_logs(self, uid: int, date: str):
        return await self.fetchall(
            "SELECT tl.*, r.title, r.category, r.difficulty FROM task_logs tl JOIN routines r ON r.id = tl.routine_id WHERE tl.user_id = ? AND tl.date = ? ORDER BY r.scheduled_time",
            (uid, date),
        )

    async def get_task_logs_range(self, uid: int, start: str, end: str):
        return await self.fetchall(
            "SELECT tl.*, r.title, r.category, r.difficulty FROM task_logs tl JOIN routines r ON r.id = tl.routine_id WHERE tl.user_id = ? AND tl.date >= ? AND tl.date <= ? ORDER BY tl.date, r.scheduled_time",
            (uid, start, end),
        )

    async def get_today_tasks_summary(self, uid: int):
        today = datetime.now().strftime("%Y-%m-%d")
        rows = await self.get_task_logs(uid, today)
        completed = sum(1 for r in rows if r["status"] in ("completed", "partial"))
        skipped = sum(1 for r in rows if r["status"] == "skipped")
        pending = sum(1 for r in rows if r["status"] == "pending")
        total = len(rows)
        return {"rows": rows, "completed": completed, "skipped": skipped, "pending": pending, "total": total}

    # ── Disciplines (gamification stats) CRUD ────────────────

    async def get_discipline(self, uid: int):
        row = await self.fetchone("SELECT * FROM disciplines WHERE user_id = ?", (uid,))
        if not row:
            await self.execute("INSERT OR IGNORE INTO disciplines (user_id) VALUES (?)", (uid,))
            return {"user_id": uid, "xp": 0, "level": 1, "discipline_score": 50,
                    "streak": 0, "longest_streak": 0, "last_active_date": "",
                    "total_completed": 0, "total_skipped": 0, "total_delayed": 0}
        return row

    async def update_discipline(self, uid: int, **kwargs):
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [uid]
        await self.execute(f"UPDATE disciplines SET {sets}, updated_at = datetime('now','localtime') WHERE user_id = ?", tuple(vals))

    async def award_xp(self, uid: int, xp: int):
        disc = await self.get_discipline(uid)
        new_xp = disc["xp"] + xp
        new_level = int((new_xp / 100) ** 0.5) + 1
        await self.update_discipline(uid, xp=new_xp, level=new_level)

    # ── Active Sessions CRUD ──────────────────────────────────

    async def get_active_session(self, uid: int):
        return await self.fetchone(
            "SELECT * FROM active_sessions WHERE user_id = ? AND status IN ('active', 'paused')", (uid,)
        )

    async def create_active_session(self, uid: int, routine_id: int, focus_mode: int = 0, focus_minutes: int = 25):
        existing = await self.get_active_session(uid)
        if existing:
            return existing["id"]
        cur = await self.execute(
            "INSERT INTO active_sessions (user_id, routine_id, focus_mode, focus_minutes) VALUES (?, ?, ?, ?)",
            (uid, routine_id, focus_mode, focus_minutes),
        )
        return cur.lastrowid

    async def update_active_session(self, uid: int, **kwargs):
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [uid]
        await self.execute(f"UPDATE active_sessions SET {sets} WHERE user_id = ?", tuple(vals))

    async def delete_active_session(self, uid: int):
        await self.execute("DELETE FROM active_sessions WHERE user_id = ?", (uid,))

    async def pause_active_session(self, uid: int):
        session = await self.get_active_session(uid)
        if session:
            await self.execute(
                "INSERT INTO pause_logs (user_id, routine_id, session_id) VALUES (?, ?, ?)",
                (uid, session["routine_id"], session["id"]),
            )
            await self.update_active_session(uid, status='paused', paused_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    async def resume_active_session(self, uid: int):
        session = await self.get_active_session(uid)
        if session and session["status"] == "paused":
            pause_log = await self.fetchone(
                "SELECT id, paused_at FROM pause_logs WHERE session_id = ? AND resumed_at IS NULL ORDER BY id DESC LIMIT 1",
                (session["id"],),
            )
            if pause_log:
                from datetime import datetime
                paused_dt = datetime.strptime(pause_log["paused_at"], "%Y-%m-%d %H:%M:%S")
                resumed_dt = datetime.now()
                delta = int((resumed_dt - paused_dt).total_seconds())
                await self.execute(
                    "UPDATE pause_logs SET resumed_at = ?, pause_seconds = ? WHERE id = ?",
                    (resumed_dt.strftime("%Y-%m-%d %H:%M:%S"), delta, pause_log["id"]),
                )
                total = (session["total_pause_seconds"] or 0) + delta
                await self.update_active_session(uid, status='active', paused_at=None, total_pause_seconds=total)

    # ── Focus Sessions CRUD ───────────────────────────────────

    async def create_focus_session(self, uid: int, routine_id: int, session_id: int, planned_minutes: int = 25):
        cur = await self.execute(
            "INSERT INTO focus_sessions (user_id, routine_id, session_id, planned_minutes) VALUES (?, ?, ?, ?)",
            (uid, routine_id, session_id, planned_minutes),
        )
        return cur.lastrowid

    async def complete_focus_session(self, fid: int):
        session = await self.get_focus_session(fid)
        if not session:
            return
        from datetime import datetime
        started = datetime.strptime(session["started_at"], "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        actual_minutes = int((now - started).total_seconds() / 60)
        await self.execute(
            "UPDATE focus_sessions SET completed = 1, completed_at = datetime('now', 'localtime'), actual_minutes = ? WHERE id = ?",
            (max(0, actual_minutes), fid),
        )

    async def get_focus_session(self, fid: int):
        return await self.fetchone("SELECT * FROM focus_sessions WHERE id = ?", (fid,))

    async def get_active_focus_session(self, uid: int):
        return await self.fetchone(
            "SELECT * FROM focus_sessions WHERE user_id = ? AND completed = 0 ORDER BY id DESC LIMIT 1", (uid,)
        )

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  timezone TEXT DEFAULT 'Asia/Tashkent',
  language TEXT DEFAULT 'uz',
  daily_calorie_limit INTEGER DEFAULT 2000,
  current_balance REAL DEFAULT 0,
  total_income REAL DEFAULT 0,
  total_expense REAL DEFAULT 0,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  priority INTEGER DEFAULT 1,
  status TEXT DEFAULT 'active',
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  UNIQUE(user_id, name),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS goal_details (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT,
  FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  day_of_week INTEGER NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  activity TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  schedule_id INTEGER DEFAULT 0,
  message TEXT NOT NULL,
  remind_time TEXT NOT NULL,
  day_of_week INTEGER DEFAULT -1,
  active INTEGER DEFAULT 1,
  job_id TEXT DEFAULT '',
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  date TEXT NOT NULL,
  completed INTEGER DEFAULT 0,
  notes TEXT DEFAULT '',
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS streaks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  current_streak INTEGER DEFAULT 0,
  longest_streak INTEGER DEFAULT 0,
  last_date TEXT DEFAULT '',
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS nutrition_goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  daily_calories INTEGER DEFAULT 2000,
  protein_grams REAL DEFAULT 0,
  fat_grams REAL DEFAULT 0,
  carb_grams REAL DEFAULT 0,
  water_ml INTEGER DEFAULT 2000,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS user_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,
  profile_json TEXT DEFAULT '{}',
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  updated_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS daily_missions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  date TEXT NOT NULL,
  missions_json TEXT DEFAULT '[]',
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS user_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  updated_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  tx_type TEXT NOT NULL CHECK(tx_type IN ('income','expense')),
  category TEXT NOT NULL DEFAULT 'other',
  description TEXT DEFAULT '',
  date TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS daily_finance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  date TEXT NOT NULL,
  total_income REAL DEFAULT 0,
  total_expense REAL DEFAULT 0,
  transaction_count INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS routines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  goal_id INTEGER DEFAULT 0,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT DEFAULT 'general',
  scheduled_time TEXT NOT NULL,
  duration_minutes INTEGER DEFAULT 30,
  difficulty TEXT DEFAULT 'medium',
  repeat_type TEXT DEFAULT 'daily',
  day_of_week TEXT DEFAULT 'daily',
  active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS task_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  routine_id INTEGER,
  date TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  completed_at TEXT,
  xp_earned INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS disciplines (
  user_id INTEGER PRIMARY KEY,
  xp INTEGER DEFAULT 0,
  level INTEGER DEFAULT 1,
  discipline_score INTEGER DEFAULT 50,
  streak INTEGER DEFAULT 0,
  longest_streak INTEGER DEFAULT 0,
  last_active_date TEXT,
  total_completed INTEGER DEFAULT 0,
  total_skipped INTEGER DEFAULT 0,
  total_delayed INTEGER DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS active_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,
  routine_id INTEGER NOT NULL,
  status TEXT DEFAULT 'active',
  started_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  paused_at TEXT,
  total_pause_seconds INTEGER DEFAULT 0,
  focus_mode INTEGER DEFAULT 0,
  focus_minutes INTEGER DEFAULT 25,
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (routine_id) REFERENCES routines(id)
);

CREATE TABLE IF NOT EXISTS pause_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  routine_id INTEGER NOT NULL,
  session_id INTEGER NOT NULL,
  paused_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  resumed_at TEXT,
  pause_seconds INTEGER DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (routine_id) REFERENCES routines(id)
);

CREATE TABLE IF NOT EXISTS focus_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  routine_id INTEGER NOT NULL,
  session_id INTEGER,
  focus_type TEXT DEFAULT 'pomodoro',
  planned_minutes INTEGER DEFAULT 25,
  actual_minutes INTEGER DEFAULT 0,
  completed INTEGER DEFAULT 0,
  started_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  completed_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""

from datetime import datetime
