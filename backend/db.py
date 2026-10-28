"""Tiny SQLite layer (stdlib only). One short-lived connection per call keeps it thread-safe under FastAPI."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS interviews (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), role TEXT, seniority TEXT,
  overall_score REAL, hiring_band TEXT, scorecard_json TEXT, history_json TEXT, turns_json TEXT,
  created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_interviews_user ON interviews(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS live_interviews (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), role TEXT,
  answered INTEGER, total INTEGER, snapshot_json TEXT NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_live_user ON live_interviews(user_id, updated_at DESC);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(os.getenv("DB_PATH") or str(Path(__file__).parent / "rehearse.db"))
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with closing(_conn()) as c:
        c.executescript(SCHEMA)
        # Older databases were created before full transcripts were saved: add the column in place.
        columns = {row["name"] for row in c.execute("PRAGMA table_info(interviews)")}
        if "turns_json" not in columns:
            c.execute("ALTER TABLE interviews ADD COLUMN turns_json TEXT")
            c.commit()


def execute(sql: str, args: tuple = ()) -> int:
    with closing(_conn()) as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid


def one(sql: str, args: tuple = ()):
    with closing(_conn()) as c:
        return c.execute(sql, args).fetchone()


def rows(sql: str, args: tuple = ()):
    with closing(_conn()) as c:
        return c.execute(sql, args).fetchall()


def delete_user(user_id: int) -> None:
    """Remove an account and everything saved under it, in one transaction."""
    with closing(_conn()) as c:
        c.execute("DELETE FROM live_interviews WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM interviews WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        c.commit()


def purge_stale_live(max_age_seconds: float) -> None:
    """Drop unfinished interviews nobody came back to."""
    import time
    execute("DELETE FROM live_interviews WHERE updated_at < ?", (time.time() - max_age_seconds,))