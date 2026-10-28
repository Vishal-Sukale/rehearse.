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

import coding  # noqa: E402
from api import app  # noqa: E402

client = TestClient(app)


def signup(email):
    r = client.post("/api/auth/signup", json={"name": "Ana", "email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def available(h):
    return {x["id"]: x["available"] for x in client.get("/api/coding/languages", headers=h).json()}


def review_body(p, passed, total, language="cpp"):
    return {
        "language": language, "title": p["title"], "statement": p["statement"], "code": p["starters"][language],
        "passed": passed, "total": total, "failures": ["input 4 / 2 7 11 15 / 9 expected 0 1, got nothing"],
        "expected_complexity": p["expected_complexity"], "reference_solution": p["reference_solution"], "seconds": 300,
    }


def test_demo_problem_and_review():
    h = signup("code1@x.co")
    p = client.post("/api/coding/problem", json={"topic": "Arrays", "difficulty": 2}, headers=h).json()
    assert isinstance(p["test_inputs"][0], str) and set(p["starters"]) == {"python", "c", "cpp", "java"}
    r = client.post("/api/coding/review", json=review_body(p, 5, 6), headers=h).json()
    assert r["correctness"] == 8.3 and r["score"] == round(7 * 8.3 + 3 * r["quality"])
    assert r["band"] in {"strong_hire", "hire", "lean_hire", "no_hire"}


def test_coding_requires_login_and_sane_results():
    assert client.post("/api/coding/problem", json={"topic": "Strings"}).status_code == 401
    h = signup("code2@x.co")
    p = client.post("/api/coding/problem", json={"topic": "Strings"}, headers=h).json()
    assert client.post("/api/coding/review", json=review_body(p, 7, 6), headers=h).status_code == 422


def test_only_python_is_offered_without_a_runner(monkeypatch):
    h = signup("code3@x.co")
    for name in ("PISTON_URL", "LOCAL_RUNNER"):
        monkeypatch.delenv(name, raising=False)
    assert available(h) == {"python": True, "c": False, "cpp": False, "java": False}


def test_languages_follow_what_the_runner_has_installed(monkeypatch):
    h = signup("code4@x.co")
    monkeypatch.delenv("LOCAL_RUNNER", raising=False)
    monkeypatch.setenv("PISTON_URL", "http://runner.test")
    monkeypatch.setattr(coding, "installed_languages", lambda url, timeout=3.0: {"c", "gcc"})
    assert available(h) == {"python": True, "c": True, "cpp": False, "java": False}
    monkeypatch.setattr(coding, "installed_languages", lambda url, timeout=3.0: None)   # the runner is down
    assert available(h) == {"python": True, "c": False, "cpp": False, "java": False}


def test_remote_run_needs_a_runner_and_never_accepts_python(monkeypatch):
    for name in ("PISTON_URL", "LOCAL_RUNNER"):
        monkeypatch.delenv(name, raising=False)
    h = signup("code5@x.co")
    body = {"language": "c", "code": "int main(){return 0;}", "inputs": ["1\n"]}
    assert client.post("/api/coding/run", json=body, headers=h).status_code == 503
    assert client.post("/api/coding/run", json={**body, "language": "python"}, headers=h).status_code == 422


def test_local_runner_works_when_enabled_and_is_blocked_in_production(monkeypatch):
    h = signup("code6@x.co")
    monkeypatch.delenv("PISTON_URL", raising=False)
    monkeypatch.setenv("LOCAL_RUNNER", "1")
    monkeypatch.setattr(coding.localrun, "available", lambda lang: lang == "cpp")
    fake = {"compile_error": None, "results": [{"stdout": "8\n", "stderr": "", "exit_code": 0, "timed_out": False}]}
    monkeypatch.setattr(coding.localrun, "run_many", lambda lang, code, inputs: fake)
    assert available(h)["cpp"] is True and available(h)["c"] is False
    body = {"language": "cpp", "code": "int main(){}", "inputs": ["4\n"]}
    assert client.post("/api/coding/run", json=body, headers=h).json() == fake
    monkeypatch.setenv("APP_ENV", "production")   # never compile on the server in production
    assert client.post("/api/coding/run", json=body, headers=h).status_code == 503
    assert available(h)["cpp"] is False