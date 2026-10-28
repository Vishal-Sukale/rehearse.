import os
import tempfile
import unittest


def use_temp_db(case):
    previous = os.environ.get("DB_PATH")
    case.addCleanup(lambda: os.environ.__setitem__("DB_PATH", previous) if previous is not None else os.environ.pop("DB_PATH", None))
    os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")


ATTEMPT = {"topic": "Arrays", "difficulty": 2, "language": "cpp", "title": "Two Sum", "code": "int main(){}", "passed": 5,
           "total": 6, "quality": 7, "score": 79, "band": "hire", "seconds": 300, "review": {"next_step": "x"}}


class ExportStoreTests(unittest.TestCase):
    def test_export_has_code_and_review_but_only_for_that_user(self):
        use_temp_db(self)
        import coding_store
        import db
        coding_store.ensure_table()
        a = db.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES ('A', 'a@x.co', 'h', 1)")
        b = db.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES ('B', 'b@x.co', 'h', 1)")
        coding_store.save(a, ATTEMPT)
        coding_store.save(b, {**ATTEMPT, "title": "Other"})
        rows = coding_store.all_for_export(a)
        self.assertEqual([r["title"] for r in rows], ["Two Sum"])
        self.assertEqual((rows[0]["code"], rows[0]["review"]["next_step"]), ("int main(){}", "x"))
        self.assertNotIn("user_id", rows[0])


class ExportApiTests(unittest.TestCase):
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

    def test_download_my_data_includes_coding_attempts(self):
        r = self.client.post("/api/auth/signup", json={"name": "Ana", "email": "export1@x.co", "password": "password123"})
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        self.client.post("/api/coding/attempts", json={**ATTEMPT, "title": "Mine"}, headers=h)
        data = self.client.get("/api/account/export", headers=h).json()
        self.assertEqual([a["title"] for a in data["coding_attempts"]], ["Mine"])
        self.assertEqual(data["coding_attempts"][0]["code"], "int main(){}")


if __name__ == "__main__":
    unittest.main()