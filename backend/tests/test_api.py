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
from fastapi.testclient import TestClient  # noqa: E402

from api import app  # noqa: E402

client = TestClient(app)
STRONG = " ".join(["word"] * 50)


def signup(email="a@b.co"):
    r = client.post("/api/auth/signup", json={"name": "Ana", "email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_requires_login():
    assert client.post("/api/interviews", json={}).status_code == 401


def test_security_headers_on_api_responses():
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_duplicate_email_and_bad_login():
    signup("dup@x.co")
    assert client.post("/api/auth/signup", json={"name": "B", "email": "DUP@x.co", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "dup@x.co", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "dup@x.co", "password": "password123"}).status_code == 200


def test_full_flow_persists_history():
    h = signup("flow@x.co")
    v = client.post("/api/interviews", json={"max_questions": 2, "topics": ["Algo"]}, headers=h).json()
    iid = v["id"]
    v = client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h).json()
    assert v["status"] == "question" and v["last_score"] > 8
    v = client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h).json()
    assert v["status"] == "complete" and len(v["history"]) == 2 and len(v["transcript"]) == 2
    assert [i["id"] for i in client.get("/api/interviews", headers=h).json()] == [iid]
    saved = client.get(f"/api/interviews/{iid}", headers=h).json()
    assert saved["scorecard"]["questions_answered"] == 2 and len(saved["transcript"]) == 2
    assert client.get("/api/stats", headers=h).json()["total"] == 1
    assert client.post(f"/api/interviews/{iid}/answer", json={"answer": "x"}, headers=h).status_code == 404


def test_users_are_isolated():
    a, b = signup("iso1@x.co"), signup("iso2@x.co")
    iid = client.post("/api/interviews", json={}, headers=a).json()["id"]
    assert client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=b).status_code == 404


def test_non_answer_is_scored_near_zero():
    h = signup("idk@x.co")
    iid = client.post("/api/interviews", json={}, headers=h).json()["id"]
    v = client.post(f"/api/interviews/{iid}/answer", json={"answer": "I don't know."}, headers=h).json()
    assert v["last_score"] < 1


def test_export_and_delete_account():
    h = signup("acct@x.co")
    iid = client.post("/api/interviews", json={"max_questions": 1}, headers=h).json()["id"]
    client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h)
    data = client.get("/api/account/export", headers=h).json()
    assert data["user"]["email"] == "acct@x.co" and len(data["interviews"]) == 1 and data["interviews"][0]["transcript"]
    assert client.request("DELETE", "/api/account", json={"password": "wrong"}, headers=h).status_code == 403
    assert client.request("DELETE", "/api/account", json={"password": "password123"}, headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert client.post("/api/auth/login", json={"email": "acct@x.co", "password": "password123"}).status_code == 401


def test_unfinished_interview_can_be_continued_after_a_server_restart():
    import api as api_module
    from interviewer.graph import build_graph

    h, other = signup("restart@x.co"), signup("restart2@x.co")
    v = client.post("/api/interviews", json={"max_questions": 3}, headers=h).json()
    iid = v["id"]

    # still running: continuing returns the same question
    same = client.post(f"/api/interviews/{iid}/continue", headers=h).json()
    assert same["question"]["text"] == v["question"]["text"] and same["chat"][-1]["kind"] == "q"

    client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h)
    assert [i["id"] for i in client.get("/api/interviews/live", headers=h).json()] == [iid]

    # simulate a restart: a brand-new graph and no in-memory owners
    api_module.graph = build_graph(api_module.llm)
    api_module.OWNERS.clear()

    assert client.post(f"/api/interviews/{iid}/continue", headers=other).status_code == 404   # not their interview
    c = client.post(f"/api/interviews/{iid}/continue", headers=h).json()
    assert c["status"] == "question" and len(c["history"]) == 1
    assert [m["kind"] for m in c["chat"]][:4] == ["q", "a", "fb", "q"]

    v = client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h).json()
    assert v["status"] == "question" and len(v["history"]) == 2
    v = client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h).json()
    assert v["status"] == "complete"
    assert client.get("/api/interviews/live", headers=h).json() == []      # finished interviews are no longer "unfinished"


def test_discarding_an_unfinished_interview():
    h = signup("discard@x.co")
    iid = client.post("/api/interviews", json={}, headers=h).json()["id"]
    assert len(client.get("/api/interviews/live", headers=h).json()) == 1
    assert client.delete(f"/api/interviews/live/{iid}", headers=h).status_code == 200
    assert client.get("/api/interviews/live", headers=h).json() == []
    assert client.post(f"/api/interviews/{iid}/answer", json={"answer": STRONG}, headers=h).status_code == 404