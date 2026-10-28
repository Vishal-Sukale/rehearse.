"""FastAPI backend: auth + per-user interview history around the LangGraph interview state machine.

Run:  uvicorn api:app --reload --port 8000        (OFFLINE=1 for no API key)
"""
import json
import logging
import os
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

load_dotenv()  # must run before auth/db read their settings

import db  # noqa: E402
from auth import account as account_router  # noqa: E402
from auth import current_user, router as auth_router  # noqa: E402
from coach import make_router as make_coach_router  # noqa: E402
from interviewer.graph import build_graph  # noqa: E402
from interviewer.resume import MAX_BYTES, ResumeError, extract_text, parse_resume  # noqa: E402
from interviewer.schemas import InterviewConfig  # noqa: E402
from interviewer.snapshot import chat_items, from_snapshot, question_payload, to_snapshot  # noqa: E402
from interviewer.stats import compute_stats  # noqa: E402
from ratelimit import RateLimiter  # noqa: E402

log = logging.getLogger("rehearse")
IS_PROD = os.getenv("APP_ENV", "development").lower() == "production"
if IS_PROD and len(os.getenv("JWT_SECRET", "")) < 32:
    raise RuntimeError("APP_ENV=production requires JWT_SECRET with at least 32 characters.")

OFFLINE = os.getenv("OFFLINE", "0") == "1"
if OFFLINE:
    from interviewer.testing import FakeLLM
    llm = FakeLLM()
else:
    from interviewer.llm import get_llm
    llm = get_llm()
if not os.getenv("JWT_SECRET"):
    print("WARNING: JWT_SECRET is not set. Using an insecure dev secret. Set it in backend/.env.")

db.init()
db.purge_stale_live(int(os.getenv("SNAPSHOT_TTL_DAYS", "7")) * 86400)   # forget unfinished interviews after a week
graph = build_graph(llm)   # in-memory checkpointer: a live interview is lost if the server restarts
OWNERS: dict[str, int] = {}  # interview_id -> user_id for interviews in progress

ai_limiter = RateLimiter(int(os.getenv("AI_RATE_LIMIT", "60")), 60)   # AI requests per user per minute

app = FastAPI(
    title="Rehearse API", version="3.0.0",
    docs_url=None if IS_PROD else "/docs", redoc_url=None, openapi_url=None if IS_PROD else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(make_coach_router(llm))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/assets/"):   # build output is content-hashed, so it can be cached forever
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def _check_ai_rate(user: dict) -> None:
    if not ai_limiter.allow(f"user:{user['id']}"):
        raise HTTPException(429, "You're going a bit fast. Please wait a few seconds and try again.")


def friendly_error(err: dict) -> str:
    """One plain-English sentence for a Pydantic validation error."""
    field = str(err["loc"][-1]).replace("_", " ").capitalize() if err.get("loc") else "Input"
    kind, ctx = err.get("type", ""), err.get("ctx") or {}
    if kind == "missing" or (kind == "string_too_short" and ctx.get("min_length") == 1):
        return f"{field} is required."
    if kind == "string_too_short":
        return f"{field} must be at least {ctx.get('min_length')} characters."
    if kind == "string_too_long":
        return f"{field} must be at most {ctx.get('max_length')} characters."
    if kind == "string_pattern_mismatch":
        return f"Please enter a valid {field.lower()}."
    return f"{field}: {err.get('msg', 'invalid value')}"


@app.exception_handler(RequestValidationError)
async def readable_validation_errors(request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": friendly_error(exc.errors()[0])})


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


def _run(interview_id: str) -> dict:
    return {"configurable": {"thread_id": interview_id}, "recursion_limit": 100}


def _transcript(turns, interview_id: str) -> list[dict]:
    """Everything needed to review an interview question by question."""
    return [
        {
            "interview_id": interview_id,
            "question": t.question.text, "topic": t.question.topic, "difficulty": t.question.difficulty,
            "follow_up": t.question.is_follow_up, "anchor": t.question.resume_anchor,
            "answer": t.answer, "score": round(t.overall_score, 1),
            "correctness": t.evaluation.correctness, "depth": t.evaluation.depth,
            "communication": t.evaluation.communication, "feedback": t.evaluation.feedback,
            "covered": t.evaluation.covered_points, "missed": t.evaluation.missed_points,
            "model_answer": t.question.reference_answer,
        }
        for t in turns
    ]


def _view(interview_id: str, result: dict) -> dict:
    values = graph.get_state(_run(interview_id)).values
    turns = values.get("turns", [])
    cfg = values.get("config")
    view = {
        "id": interview_id,
        "ability": round(values.get("ability", 0.0), 2),
        "answered": len(turns),
        "history": [{"difficulty": t.question.difficulty, "score": round(t.overall_score, 1)} for t in turns],
    }
    if turns:
        view["last_score"] = round(turns[-1].overall_score, 1)
        if cfg and cfg.practice_mode:
            view["feedback"] = values.get("last_feedback")
            view["model_answer"] = turns[-1].question.reference_answer or None
    if "__interrupt__" in result:
        view.update(status="question", question=result["__interrupt__"][0].value)
    else:
        view.update(status="complete", scorecard=result["scorecard"].model_dump(mode="json"), transcript=_transcript(turns, interview_id))
    return view


def _persist(interview_id: str, user_id: int, view: dict) -> None:
    card = view["scorecard"]
    if card["questions_answered"] == 0:
        return
    db.execute(
        "INSERT OR REPLACE INTO interviews (id, user_id, role, seniority, overall_score, hiring_band,"
        " scorecard_json, history_json, turns_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (interview_id, user_id, card["role"], card["seniority"], card["overall_score"], card["hiring_band"],
         json.dumps(card), json.dumps(view["history"]), json.dumps(view["transcript"]), time.time()),
    )


def _save_live(interview_id: str, user_id: int) -> None:
    """Snapshot an interview that is waiting for the candidate's answer, so it survives a server restart."""
    try:
        values = graph.get_state(_run(interview_id)).values
        cfg = values["config"]
        db.execute(
            "INSERT OR REPLACE INTO live_interviews (id, user_id, role, answered, total, snapshot_json, updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (interview_id, user_id, cfg.role, len(values.get("turns", [])), cfg.max_questions,
             json.dumps(to_snapshot(values)), time.time()),
        )
    except Exception:  # noqa: BLE001 - a snapshot problem must never break a live interview
        log.exception("Could not save a snapshot of interview %s", interview_id)


def _restore(interview_id: str, user: dict):
    """Rebuild an interview from its snapshot after a restart. Returns the graph result (paused on the
    current question), or None if there is nothing to restore."""
    row = db.one("SELECT snapshot_json FROM live_interviews WHERE id = ? AND user_id = ?", (interview_id, user["id"]))
    if not row:
        return None
    try:
        run = _run(interview_id)
        graph.update_state(run, from_snapshot(json.loads(row["snapshot_json"])), as_node="generate_question")
        result = graph.invoke(None, run)   # runs await_answer, which pauses on the question again
    except Exception:  # noqa: BLE001
        log.exception("Could not restore interview %s", interview_id)
        return None
    if "__interrupt__" not in result:
        return None
    OWNERS[interview_id] = user["id"]
    return result


def _invoke(interview_id: str, payload, user: dict) -> dict:
    try:
        view = _view(interview_id, graph.invoke(payload, _run(interview_id)))
    except RuntimeError as err:  # structured output failed after retries
        raise HTTPException(502, "The AI model returned invalid output. Please try again.") from err
    if view["status"] == "complete":
        _persist(interview_id, user["id"], view)
        OWNERS.pop(interview_id, None)
        db.execute("DELETE FROM live_interviews WHERE id = ?", (interview_id,))
    else:
        _save_live(interview_id, user["id"])
    return view


def _resume(interview_id: str, text: str, user: dict) -> dict:
    _check_ai_rate(user)
    if OWNERS.get(interview_id) != user["id"] and _restore(interview_id, user) is None:
        raise HTTPException(404, "Interview not found or already finished.")
    return _invoke(interview_id, Command(resume=text), user)


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "offline" if OFFLINE else "live"}


@app.post("/api/resume")
async def upload_resume(request: Request, filename: str = "resume.pdf", user: dict = Depends(current_user)):
    """Raw file bytes in the request body (no multipart dependency). Returns the parsed profile for review.
    The file itself is not stored; only the parsed profile travels with the interview."""
    _check_ai_rate(user)
    if int(request.headers.get("content-length") or 0) > MAX_BYTES + 4096:
        raise HTTPException(413, "That file is larger than 5 MB.")
    data = await request.body()

    def work():
        return parse_resume(llm, extract_text(filename, data))

    try:
        profile = await run_in_threadpool(work)
    except ResumeError as err:
        raise HTTPException(400, str(err)) from err
    return profile.model_dump(mode="json")


@app.post("/api/interviews")
def start_interview(config: InterviewConfig, user: dict = Depends(current_user)):
    _check_ai_rate(user)
    interview_id = uuid.uuid4().hex
    OWNERS[interview_id] = user["id"]
    try:
        return _invoke(interview_id, {"config": config}, user)
    except HTTPException:
        OWNERS.pop(interview_id, None)
        raise


@app.post("/api/interviews/{interview_id}/answer")
def submit_answer(interview_id: str, body: AnswerRequest, user: dict = Depends(current_user)):
    return _resume(interview_id, body.answer, user)


@app.post("/api/interviews/{interview_id}/end")
def end_interview(interview_id: str, user: dict = Depends(current_user)):
    return _resume(interview_id, "/end", user)


@app.get("/api/interviews")
def list_interviews(user: dict = Depends(current_user)):
    rows = db.rows(
        "SELECT id, role, seniority, overall_score, hiring_band, created_at FROM interviews"
        " WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user["id"],))
    return [dict(r) for r in rows]


@app.get("/api/interviews/live")
def list_live(user: dict = Depends(current_user)):
    """Unfinished interviews the user can continue."""
    rows = db.rows(
        "SELECT id, role, answered, total, updated_at FROM live_interviews WHERE user_id = ?"
        " ORDER BY updated_at DESC LIMIT 10", (user["id"],))
    return [dict(r) for r in rows]


@app.post("/api/interviews/{interview_id}/continue")
def continue_interview(interview_id: str, user: dict = Depends(current_user)):
    """Reopen an unfinished interview, restoring it first if the server restarted since."""
    _check_ai_rate(user)
    if OWNERS.get(interview_id) == user["id"]:
        values = graph.get_state(_run(interview_id)).values
        result = {"__interrupt__": [SimpleNamespace(value=question_payload(values))]}
    else:
        result = _restore(interview_id, user)
        if result is None:
            raise HTTPException(404, "That interview can no longer be continued. Please start a new one.")
        values = graph.get_state(_run(interview_id)).values
    view = _view(interview_id, result)
    view["chat"] = chat_items(values)
    return view


@app.delete("/api/interviews/live/{interview_id}")
def discard_live(interview_id: str, user: dict = Depends(current_user)):
    db.execute("DELETE FROM live_interviews WHERE id = ? AND user_id = ?", (interview_id, user["id"]))
    if OWNERS.get(interview_id) == user["id"]:
        OWNERS.pop(interview_id, None)
    return {"ok": True}


@app.get("/api/stats")
def stats(user: dict = Depends(current_user)):
    rows = db.rows(
        "SELECT id, role, overall_score, scorecard_json, created_at FROM interviews WHERE user_id = ?", (user["id"],))
    return compute_stats([dict(r) for r in rows])


@app.get("/api/interviews/{interview_id}")
def get_interview(interview_id: str, user: dict = Depends(current_user)):
    row = db.one("SELECT * FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user["id"]))
    if not row:
        raise HTTPException(404, "Interview not found.")
    return {"id": row["id"], "status": "complete",
            "scorecard": json.loads(row["scorecard_json"]), "history": json.loads(row["history_json"]),
            "transcript": json.loads(row["turns_json"] or "[]")}


@app.delete("/api/interviews/{interview_id}")
def delete_interview(interview_id: str, user: dict = Depends(current_user)):
    db.execute("DELETE FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user["id"]))
    return {"ok": True}


# ---- Serve the built frontend (npm run build) from this same server: one URL for desktop and phone.
# Must stay LAST so it never shadows an API route.
STATIC_DIR = Path(os.getenv("STATIC_DIR") or Path(__file__).resolve().parent.parent / "frontend" / "dist")
if (STATIC_DIR / "index.html").exists():
    if (STATIC_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        root = STATIC_DIR.resolve()
        candidate = (root / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:   # root files: icon, manifest, service worker
            return FileResponse(candidate, headers={"Cache-Control": "no-cache"} if candidate.name == "sw.js" else None)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})