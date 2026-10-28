"""Signup / login with scrypt password hashes and signed JWTs (7-day expiry), plus data export and account deletion."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import coding_store
import db
from ratelimit import RateLimiter

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
TOKEN_TTL = 7 * 24 * 3600
bearer = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/api/auth", tags=["auth"])
account = APIRouter(prefix="/api/account", tags=["account"])
auth_limiter = RateLimiter(int(os.getenv("AUTH_RATE_LIMIT", "20")), 300)   # attempts per IP per 5 minutes


def client_ip(request: Request) -> str:
    if os.getenv("TRUST_PROXY") == "1":   # behind a reverse proxy / hosting platform
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit_auth(request: Request) -> None:
    if not auth_limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")


def _secret() -> str:
    return os.getenv("JWT_SECRET") or "dev-only-insecure-secret"


def _hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"{salt.hex()}${digest.hex()}"


def _verify(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    return hmac.compare_digest(_hash(password, bytes.fromhex(salt_hex)).split("$")[1], digest_hex)


def _issue(user) -> dict:
    token = jwt.encode({"sub": str(user["id"]), "exp": int(time.time()) + TOKEN_TTL}, _secret(), algorithm="HS256")
    return {"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"]}}


class Signup(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(pattern=EMAIL, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=120)
    password: str = Field(min_length=1, max_length=128)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not cred:
        raise HTTPException(401, "Please sign in.")
    try:
        user_id = int(jwt.decode(cred.credentials, _secret(), algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Your session expired. Please sign in again.")
    row = db.one("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
    if not row:
        raise HTTPException(401, "Account not found. Please sign in again.")
    return dict(row)


@router.post("/signup", dependencies=[Depends(limit_auth)])
def signup(body: Signup):
    try:
        uid = db.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?,?,?,?)",
            (body.name.strip(), body.email.lower(), _hash(body.password), time.time()),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists. Try signing in.")
    return _issue({"id": uid, "name": body.name.strip(), "email": body.email.lower()})


@router.post("/login", dependencies=[Depends(limit_auth)])
def login(body: Login):
    row = db.one("SELECT * FROM users WHERE email = ?", (body.email.lower(),))
    if not row or not _verify(body.password, row["password_hash"]):
        raise HTTPException(401, "Incorrect email or password.")
    return _issue(row)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user


class DeleteAccount(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@account.get("/export")
def export_data(user: dict = Depends(current_user)):
    """Everything we store about the user, as JSON (their account, scorecards, answer transcripts and coding attempts)."""
    rows = db.rows("SELECT * FROM interviews WHERE user_id = ? ORDER BY created_at", (user["id"],))
    return {
        "user": user,
        "interviews": [
            {
                "id": r["id"], "created_at": r["created_at"], "role": r["role"], "seniority": r["seniority"],
                "overall_score": r["overall_score"], "scorecard": json.loads(r["scorecard_json"] or "{}"),
                "history": json.loads(r["history_json"] or "[]"), "transcript": json.loads(r["turns_json"] or "[]"),
            }
            for r in rows
        ],
        "coding_attempts": coding_store.all_for_export(user["id"]),
    }


@account.delete("", dependencies=[Depends(limit_auth)])
def delete_account(body: DeleteAccount, user: dict = Depends(current_user)):
    row = db.one("SELECT password_hash FROM users WHERE id = ?", (user["id"],))
    if not row or not _verify(body.password, row["password_hash"]):
        raise HTTPException(403, "Incorrect password.")
    db.delete_user(user["id"])
    return {"ok": True}