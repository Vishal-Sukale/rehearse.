"""Saved coding attempts: save after a review, list, progress stats, one attempt, delete."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

import coding_store as store
from auth import current_user
from interviewer.coding_kit import coding_score
from interviewer.coding_stats import coding_stats
from interviewer.scoring import hiring_band


class AttemptIn(BaseModel):
    topic: str = Field("", max_length=80)
    difficulty: int = Field(3, ge=1, le=5)
    language: Literal["python", "c", "cpp", "java"]
    title: str = Field(max_length=100)
    code: str = Field(min_length=1, max_length=8000)
    passed: int = Field(ge=0, le=50)
    total: int = Field(ge=1, le=50)
    quality: int = Field(ge=0, le=10)
    seconds: int = Field(0, ge=0, le=86400)
    review: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sane(self):
        if self.passed > self.total:
            raise ValueError("passed cannot be more than total")
        if len(json.dumps(self.review)) > 6000:
            raise ValueError("review is too large")
        return self


def make_router() -> APIRouter:
    store.ensure_table()
    router = APIRouter(prefix="/api/coding/attempts", tags=["coding history"])

    @router.post("")
    def save_attempt(body: AttemptIn, user: dict = Depends(current_user)):
        _, score = coding_score(body.passed, body.total, body.quality)   # the server computes the score itself
        band = hiring_band(score)
        attempt_id = store.save(user["id"], {**body.model_dump(), "score": score, "band": band})
        return {"id": attempt_id, "score": score, "band": band}

    @router.get("")
    def list_attempts(user: dict = Depends(current_user)):
        return store.list_for(user["id"])

    @router.get("/stats")
    def attempt_stats(user: dict = Depends(current_user)):
        return coding_stats(store.all_for_stats(user["id"]))

    @router.get("/{attempt_id}")
    def get_attempt(attempt_id: str, user: dict = Depends(current_user)):
        attempt = store.get(user["id"], attempt_id)
        if not attempt:
            raise HTTPException(404, "Attempt not found.")
        return attempt

    @router.delete("/{attempt_id}")
    def delete_attempt(attempt_id: str, user: dict = Depends(current_user)):
        store.delete(user["id"], attempt_id)
        return {"ok": True}

    return router