import os
import tempfile

import pytest

# setdefault: if another test module already imported the app, keep its database and settings.
os.environ.setdefault("OFFLINE", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-12345")
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("AUTH_RATE_LIMIT", "1000")
pytest.importorskip("fastapi")
pytest.importorskip("langgraph")
pytest.importorskip("jwt")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import app  # noqa: E402
from coach import AnswerCoaching, make_router  # noqa: E402

client = TestClient(app)
STRONG = " ".join(["word"] * 50)


class StubLLM:
    """Returns a fixed coaching result, so the endpoint can be tested without a real model."""

    def with_structured_output(self, schema):
        assert schema is AnswerCoaching

        class Runnable:
            def invoke(self, messages):
                return AnswerCoaching(
                    improved_answer="I would lead with the main point, then explain the trade-off. For example [metric].",
                    what_changed=["Led with the conclusion"],
                    next_time_tip="Pause for a second before you start.",
                )

        return Runnable()


def signup(email):
    r = client.post("/api/auth/signup", json={"name": "Ana", "email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_coach_rewrites_a_saved_answer(monkeypatch):
    monkeypatch.setenv("OFFLINE", "0")
    h = signup("coach1@x.co")
    iid = client.post("/api/interviews", json={"max_questions": 1}, headers=h).json()["id"]
    client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h)   # one question: finishes and saves
    saved = client.get(f"/api/interviews/{iid}", headers=h).json()
    assert saved["transcript"][0]["interview_id"] == iid

    small = FastAPI()
    small.include_router(make_router(StubLLM()))
    c = TestClient(small)
    r = c.post(f"/api/interviews/{iid}/coach", json={"index": 0}, headers=h)
    assert r.status_code == 200 and r.json()["improved_answer"].startswith("I would lead")
    assert c.post(f"/api/interviews/{iid}/coach", json={"index": 5}, headers=h).status_code == 404
    other = signup("coach2@x.co")
    assert c.post(f"/api/interviews/{iid}/coach", json={"index": 0}, headers=other).status_code == 404


def test_coach_is_unavailable_in_demo_mode():
    h = signup("coach3@x.co")
    assert client.post("/api/interviews/nope/coach", json={"index": 0}, headers=h).status_code == 503