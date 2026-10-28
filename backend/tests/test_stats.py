import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone


def ts(y, m, d):
    return datetime(y, m, d, 12, tzinfo=timezone.utc).timestamp()


def row(i, when, score, topics):
    card = {
        "topic_breakdown": [{"topic": t, "average_score": s, "questions": q} for t, s, q in topics],
        "dimension_averages": {"correctness": 7.0, "depth": 5.0, "communication": 8.0},
    }
    return {"id": f"i{i}", "created_at": when, "overall_score": score, "role": "Backend", "scorecard_json": json.dumps(card)}


class StatsTests(unittest.TestCase):
    def setUp(self):
        from interviewer.stats import compute_stats
        self.compute = compute_stats

    def test_empty(self):
        s = self.compute([], today=date(2026, 10, 21))
        self.assertEqual((s["total"], s["average"], s["streak_days"], s["topics"]), (0, None, 0, []))

    def test_summary_and_weakest_topic_first(self):
        rows = [row(1, ts(2026, 10, 18), 50, [("SQL", 4.0, 2), ("APIs", 8.0, 1)]),
                row(2, ts(2026, 10, 20), 70, [("SQL", 6.0, 2)])]
        s = self.compute(rows, today=date(2026, 10, 21))
        self.assertEqual((s["total"], s["average"], s["best"], s["latest"], s["change_since_first"]), (2, 60.0, 70.0, 70.0, 20.0))
        self.assertEqual(s["topics"][0]["topic"], "SQL")        # (4*2 + 6*2) / 4 = 5.0, weakest
        self.assertEqual(s["topics"][0]["score"], 5.0)
        self.assertEqual(s["dimensions"]["depth"], 5.0)

    def test_streak_counts_consecutive_days_ending_today_or_yesterday(self):
        rows = [row(i, ts(2026, 10, d), 60, [("A", 6, 1)]) for i, d in enumerate([18, 19, 20], 1)]
        self.assertEqual(self.compute(rows, today=date(2026, 10, 21))["streak_days"], 3)   # yesterday still counts
        self.assertEqual(self.compute(rows, today=date(2026, 10, 23))["streak_days"], 0)   # gap breaks it

    def test_bad_json_is_ignored(self):
        r = row(1, ts(2026, 10, 20), 60, [])
        r["scorecard_json"] = "{not json"
        self.assertEqual(self.compute([r], today=date(2026, 10, 21))["total"], 1)


class MigrationTests(unittest.TestCase):
    def test_adds_turns_column_to_an_old_database(self):
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        c = sqlite3.connect(path)
        c.executescript("""CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, password_hash TEXT, created_at REAL);
          CREATE TABLE interviews (id TEXT PRIMARY KEY, user_id INTEGER, role TEXT, seniority TEXT, overall_score REAL,
          hiring_band TEXT, scorecard_json TEXT, history_json TEXT, created_at REAL NOT NULL);
          INSERT INTO interviews (id, user_id, created_at) VALUES ('x', 1, 1.0);""")
        c.commit(); c.close()
        previous = os.environ.get("DB_PATH")   # restore afterwards so other tests keep their own database
        self.addCleanup(lambda: os.environ.__setitem__("DB_PATH", previous) if previous is not None else os.environ.pop("DB_PATH", None))
        os.environ["DB_PATH"] = path
        import db
        db.init(); db.init()   # idempotent
        self.assertIn("turns_json", db.one("SELECT * FROM interviews").keys())
        db.execute("UPDATE interviews SET turns_json = ? WHERE id = 'x'", ("[]",))
        self.assertEqual(db.one("SELECT turns_json FROM interviews")["turns_json"], "[]")


if __name__ == "__main__":
    unittest.main()