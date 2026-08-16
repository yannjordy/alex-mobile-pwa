import json
import os
import sqlite3
from datetime import date, datetime
from typing import Any, Optional

MEMORY_DIR = os.environ.get("ALEX_MEMORY_DIR", "/mnt/models/alex-memory")
os.makedirs(MEMORY_DIR, exist_ok=True)
DB_PATH = os.path.join(MEMORY_DIR, "alex_memory.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    with _conn() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                confidence REAL DEFAULT 1.0,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS daily_learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL UNIQUE,
                summary TEXT NOT NULL,
                interactions INTEGER DEFAULT 0,
                new_facts INTEGER DEFAULT 0,
                topics TEXT DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS experience (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL UNIQUE,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                total_interactions INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at DESC);
        """)


# --- Conversations ---

def save_conversation(role: str, content: str, source: Optional[str] = None):
    with _conn() as db:
        db.execute(
            "INSERT INTO conversations (role, content, source) VALUES (?, ?, ?)",
            (role, content, source),
        )


def get_recent_conversations(limit: int = 20) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def clear_conversations():
    with _conn() as db:
        db.execute("DELETE FROM conversations")


def delete_conversation_range(start_id: int, end_id: int):
    with _conn() as db:
        db.execute("DELETE FROM conversations WHERE id >= ? AND id <= ?", (start_id, end_id))


# --- Facts (mémoire longue durée) ---

def save_fact(key: str, value: str, category: str = "general", confidence: float = 1.0, source: Optional[str] = None):
    with _conn() as db:
        db.execute(
            """INSERT INTO facts (key, value, category, confidence, source, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value,
                   category=excluded.category,
                   confidence=excluded.confidence,
                   source=excluded.source,
                   updated_at=datetime('now','localtime')""",
            (key, value, category, confidence, source),
        )


def get_fact(key: str) -> Optional[dict]:
    with _conn() as db:
        r = db.execute("SELECT * FROM facts WHERE key = ?", (key,)).fetchone()
        return dict(r) if r else None


def get_all_facts() -> list[dict]:
    with _conn() as db:
        return [dict(r) for r in db.execute("SELECT * FROM facts ORDER BY updated_at DESC").fetchall()]


def delete_fact(key: str):
    with _conn() as db:
        db.execute("DELETE FROM facts WHERE key = ?", (key,))


# --- Daily Learnings ---

def _today() -> str:
    return date.today().isoformat()


def record_interaction():
    with _conn() as db:
        today = _today()
        existing = db.execute(
            "SELECT * FROM daily_learnings WHERE day = ?", (today,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE daily_learnings SET interactions = interactions + 1 WHERE day = ?",
                (today,),
            )
        else:
            db.execute(
                "INSERT INTO daily_learnings (day, summary, interactions) VALUES (?, ?, 1)",
                (today, f"Journée du {today}"),
            )


def record_learning(summary: str, topics: Optional[list[str]] = None):
    with _conn() as db:
        today = _today()
        existing = db.execute(
            "SELECT * FROM daily_learnings WHERE day = ?", (today,)
        ).fetchone()
        if existing:
            old_topics = json.loads(existing["topics"] or "[]")
            merged = list(set(old_topics + (topics or [])))
            db.execute(
                """UPDATE daily_learnings
                   SET summary = ?, new_facts = new_facts + 1, topics = ?
                   WHERE day = ?""",
                (summary, json.dumps(merged), today),
            )
        else:
            db.execute(
                "INSERT INTO daily_learnings (day, summary, new_facts, topics) VALUES (?, ?, 1, ?)",
                (today, summary, json.dumps(topics or [])),
            )


def get_today_learning() -> Optional[dict]:
    with _conn() as db:
        r = db.execute(
            "SELECT * FROM daily_learnings WHERE day = ?", (_today(),)
        ).fetchone()
        return dict(r) if r else None


def get_recent_learnings(days: int = 7) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM daily_learnings ORDER BY day DESC LIMIT ?",
            (days,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Experience / Level ---

def add_xp(amount: int = 10):
    with _conn() as db:
        today = _today()
        existing = db.execute(
            "SELECT * FROM experience WHERE day = ?", (today,)
        ).fetchone()
        if existing:
            total_xp = existing["xp"] + amount
            total_interactions = existing["total_interactions"] + 1
            level = min(total_xp // 100 + 1, 100)
            db.execute(
                "UPDATE experience SET xp = ?, level = ?, total_interactions = ? WHERE day = ?",
                (total_xp, level, total_interactions, today),
            )
        else:
            db.execute(
                "INSERT INTO experience (day, level, xp, total_interactions) VALUES (?, 1, ?, 1)",
                (today, amount),
            )


def get_level() -> dict:
    with _conn() as db:
        row = db.execute(
            "SELECT SUM(xp) as total_xp, SUM(total_interactions) as interactions FROM experience"
        ).fetchone()
        total_xp = row["total_xp"] or 0
        level = min(total_xp // 100 + 1, 100)
        next_at = (level * 100) - total_xp
        return {
            "level": level,
            "xp": total_xp,
            "xp_to_next": max(0, next_at),
            "total_interactions": row["interactions"] or 0,
        }


# --- Initialisation ---

init()
