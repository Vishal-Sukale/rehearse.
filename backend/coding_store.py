"""Storage for saved coding attempts (SQLite, through db.py). The table is created on demand, and a trigger removes a
user's attempts when their account is deleted, so db.delete_user needs no changes."""
import json
import secrets
import time

import db


def ensure_table() -> None:
    db.init()
    db.execute(
        """CREATE TABLE IF NOT EXISTS coding_attempts (
        id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), topic TEXT, difficulty INTEGER,
        language TEXT, title TEXT, code TEXT, passed INTEGER, total INTEGER, quality INTEGER, score INTEGER,
        band TEXT, seconds INTEGER, review_json TEXT, created_at REAL NOT NULL)"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_coding_user ON coding_attempts(user_id, created_at DESC)")
    db.execute(
        """CREATE TRIGGER IF NOT EXISTS coding_attempts_cleanup AFTER DELETE ON users
        BEGIN DELETE FROM coding_attempts WHERE user_id = OLD.id; END"""
    )


def save(user_id: int, a: dict) -> str:
    attempt_id = secrets.token_hex(8)
    db.execute(
        "INSERT INTO coding_attempts (id, user_id, topic, difficulty, language, title, code, passed, total, quality,"
        " score, band, seconds, review_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (attempt_id, user_id, a["topic"], a["difficulty"], a["language"], a["title"], a["code"], a["passed"], a["total"],
         a["quality"], a["score"], a["band"], a["seconds"], json.dumps(a["review"]), time.time()),
    )
    return attempt_id


def list_for(user_id: int, limit: int = 100) -> list[dict]:
    rows = db.rows(
        "SELECT id, topic, difficulty, language, title, passed, total, score, band, seconds, created_at"
        " FROM coding_attempts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
    return [dict(r) for r in rows]


def all_for_stats(user_id: int) -> list[dict]:
    rows = db.rows(
        "SELECT id, topic, language, title, passed, total, score, seconds, created_at FROM coding_attempts WHERE user_id = ?",
        (user_id,))
    return [dict(r) for r in rows]


def get(user_id: int, attempt_id: str) -> dict | None:
    row = db.one("SELECT * FROM coding_attempts WHERE id = ? AND user_id = ?", (attempt_id, user_id))
    if not row:
        return None
    data = dict(row)
    data["review"] = json.loads(data.pop("review_json") or "{}")
    return data


def delete(user_id: int, attempt_id: str) -> None:
    db.execute("DELETE FROM coding_attempts WHERE id = ? AND user_id = ?", (attempt_id, user_id))


def all_for_export(user_id: int) -> list[dict]:
    """Everything stored about a user's coding attempts, for the 'Download my data' file."""
    ensure_table()
    out = []
    for r in db.rows("SELECT * FROM coding_attempts WHERE user_id = ? ORDER BY created_at", (user_id,)):
        data = dict(r)
        data["review"] = json.loads(data.pop("review_json") or "{}")
        data.pop("user_id", None)
        out.append(data)
    return out