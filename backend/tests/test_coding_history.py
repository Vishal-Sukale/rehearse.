import os
import tempfile
import unittest

from interviewer.coding_stats import coding_stats


def use_temp_db(case):
    previous = os.environ.get("DB_PATH")
    case.addCleanup(lambda: os.environ.__setitem__("DB_PATH", previous) if previous is not None else os.environ.pop("DB_PATH", None))
    os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")


def row(i, ts, score, passed=5, total=6, topic="Strings", language="python"):
    return {"id": f"a{i}", "created_at": ts, "score": score, "passed": passed, "total": total,
            "topic": topic, "language": language, "title": f"P{i}", "seconds": 600}


class StatsTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(coding_stats([])["total"], 0)

    def test_summary_and_weakest_topic_first(self):
        s = coding_stats([row(1, 1, 50), row(2, 2, 90, passed=6, topic="Arrays"), row(3, 3, 70, language="cpp")])
        self.assertEqual((s["total"], s["average"], s["best"], s["latest"], s["solved"], s["solve_rate"]), (3, 70.0, 90, 70, 1, 33))
        self.assertEqual(s["topics"][0], {"name": "Strings", "average": 60.0, "attempts": 2})
        self.assertEqual({x["name"] for x in s["languages"]}, {"python", "cpp"})
        self.assertEqual(s["avg_minutes"], 10.0)


class StoreTests(unittest.TestCase):
    def setUp(self):
        use_temp_db(self)
        import coding_store
        import db
        self.db, self.store = db, coding_store
        coding_store.ensure_table()
        coding_store.ensure_table()   # safe to run on every start
        self.a = db.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES ('A', 'a@x.co', 'h', 1)")
        self.b = db.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES ('B', 'b@x.co', 'h', 1)")

    def attempt(self, title="Two Sum"):
        return {"topic": "Arrays", "difficulty": 2, "language": "cpp", "title": title, "code": "int main(){}", "passed": 5,
                "total": 6, "quality": 7, "score": 79, "band": "hire", "seconds": 300, "review": {"next_step": "x"}}

    def test_save_list_get_delete_and_isolation(self):
        aid = self.store.save(self.a, self.attempt())
        self.assertEqual([r["id"] for r in self.store.list_for(self.a)], [aid])
        self.assertEqual(self.store.list_for(self.b), [])
        self.assertEqual(self.store.get(self.a, aid)["review"]["next_step"], "x")
        self.assertIsNone(self.store.get(self.b, aid))
        self.store.delete(self.b, aid)                    # someone else's attempt: nothing happens
        self.assertIsNotNone(self.store.get(self.a, aid))
        self.store.delete(self.a, aid)
        self.assertIsNone(self.store.get(self.a, aid))

    def test_deleting_an_account_removes_its_attempts(self):
        self.store.save(self.a, self.attempt())
        self.store.save(self.b, self.attempt("Other"))
        self.db.delete_user(self.a)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM coding_attempts WHERE user_id = ?", (self.a,))["n"], 0)
        self.assertEqual(len(self.store.list_for(self.b)), 1)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            os.environ.setdefault("OFFLINE", "1")
            os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-12345")
            os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
            os.environ.setdefault("AUTH_RATE_LIMIT", "1000")
            from fastapi.testclient import TestClient

            from api import app
        except ImportError as err:
            raise unittest.SkipTest(f"API dependencies not installed: {err}")
        cls.client = TestClient(app)

    def signup(self, email):
        r = self.client.post("/api/auth/signup", json={"name": "Ana", "email": email, "password": "password123"})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": f"Bearer {r.json()['token']}"}

    def body(self, **over):
        return {"topic": "Arrays", "difficulty": 2, "language": "cpp", "title": "Two Sum", "code": "int main(){}",
                "passed": 5, "total": 6, "quality": 7, "seconds": 300, "review": {"next_step": "x"}, **over}

    def test_save_list_detail_stats_and_delete(self):
        h = self.signup("hist1@x.co")
        saved = self.client.post("/api/coding/attempts", json=self.body(), headers=h).json()
        self.assertEqual(saved["score"], 79)   # computed by the server: 70% tests, 30% quality
        self.assertEqual([a["id"] for a in self.client.get("/api/coding/attempts", headers=h).json()], [saved["id"]])
        self.assertEqual(self.client.get(f"/api/coding/attempts/{saved['id']}", headers=h).json()["code"], "int main(){}")
        self.assertEqual(self.client.get("/api/coding/attempts/stats", headers=h).json()["total"], 1)
        self.assertEqual(self.client.delete(f"/api/coding/attempts/{saved['id']}", headers=h).status_code, 200)
        self.assertEqual(self.client.get("/api/coding/attempts", headers=h).json(), [])

    def test_private_and_validated(self):
        a, b = self.signup("hist2@x.co"), self.signup("hist3@x.co")
        saved = self.client.post("/api/coding/attempts", json=self.body(), headers=a).json()
        self.assertEqual(self.client.get(f"/api/coding/attempts/{saved['id']}", headers=b).status_code, 404)
        self.assertEqual(self.client.post("/api/coding/attempts", json=self.body(passed=9), headers=a).status_code, 422)
        self.assertEqual(self.client.get("/api/coding/attempts").status_code, 401)


if __name__ == "__main__":
    unittest.main()