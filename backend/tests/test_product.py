import os
import tempfile
import unittest


class RateLimiterTests(unittest.TestCase):
    def test_blocks_after_the_limit_and_recovers_after_the_window(self):
        from ratelimit import RateLimiter
        now = [0.0]
        limiter = RateLimiter(3, 10, clock=lambda: now[0])
        self.assertEqual([limiter.allow("a") for _ in range(4)], [True, True, True, False])
        self.assertTrue(limiter.allow("b"))      # other visitors are unaffected
        now[0] = 11
        self.assertTrue(limiter.allow("a"))      # the window has passed

    def test_blocked_attempts_do_not_extend_the_block(self):
        from ratelimit import RateLimiter
        now = [0.0]
        limiter = RateLimiter(1, 10, clock=lambda: now[0])
        self.assertTrue(limiter.allow("a"))
        for t in (2, 4, 6, 8):
            now[0] = t
            self.assertFalse(limiter.allow("a"))
        now[0] = 10.5
        self.assertTrue(limiter.allow("a"))


class DeleteUserTests(unittest.TestCase):
    def test_removes_the_user_and_only_their_interviews(self):
        previous = os.environ.get("DB_PATH")
        self.addCleanup(lambda: os.environ.__setitem__("DB_PATH", previous) if previous is not None else os.environ.pop("DB_PATH", None))
        os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
        import db
        db.init()
        a = db.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES ('A', 'a@x.co', 'h', 1)")
        b = db.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES ('B', 'b@x.co', 'h', 1)")
        db.execute("INSERT INTO interviews (id, user_id, created_at) VALUES ('1', ?, 1)", (a,))
        db.execute("INSERT INTO interviews (id, user_id, created_at) VALUES ('2', ?, 1)", (b,))
        db.execute("INSERT INTO live_interviews (id, user_id, snapshot_json, updated_at) VALUES ('L1', ?, '{}', 1)", (a,))
        db.execute("INSERT INTO live_interviews (id, user_id, snapshot_json, updated_at) VALUES ('L2', ?, '{}', 1)", (b,))
        db.delete_user(a)
        self.assertIsNone(db.one("SELECT 1 FROM users WHERE id = ?", (a,)))
        self.assertEqual([r["id"] for r in db.rows("SELECT id FROM interviews")], ["2"])
        self.assertIsNotNone(db.one("SELECT 1 FROM users WHERE id = ?", (b,)))
        self.assertEqual([r["id"] for r in db.rows("SELECT id FROM live_interviews")], ["L2"])   # unfinished ones go too


class LiveInterviewTests(unittest.TestCase):
    def test_stale_unfinished_interviews_are_purged(self):
        import time
        previous = os.environ.get("DB_PATH")
        self.addCleanup(lambda: os.environ.__setitem__("DB_PATH", previous) if previous is not None else os.environ.pop("DB_PATH", None))
        os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
        import db
        db.init()
        uid = db.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES ('A', 'a@x.co', 'h', 1)")
        now = time.time()
        db.execute("INSERT INTO live_interviews (id, user_id, snapshot_json, updated_at) VALUES ('old', ?, '{}', ?)", (uid, now - 9 * 86400))
        db.execute("INSERT INTO live_interviews (id, user_id, snapshot_json, updated_at) VALUES ('new', ?, '{}', ?)", (uid, now - 3600))
        db.purge_stale_live(7 * 86400)
        self.assertEqual([r["id"] for r in db.rows("SELECT id FROM live_interviews")], ["new"])


if __name__ == "__main__":
    unittest.main()