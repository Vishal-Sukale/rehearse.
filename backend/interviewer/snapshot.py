"""Save and restore an interview that is waiting for an answer, so a server restart doesn't lose it.

A snapshot holds exactly the state the graph needs to continue: the config, the running ability and difficulty,
the counters, the question being asked and every graded turn so far.
"""
from .schemas import InterviewConfig, Question, TurnRecord


def to_snapshot(values: dict) -> dict:
    return {
        "config": values["config"].model_dump(mode="json"),
        "ability": values["ability"],
        "difficulty": values["difficulty"],
        "main_question_count": values["main_question_count"],
        "follow_ups_used": values["follow_ups_used"],
        "current_question": values["current_question"].model_dump(mode="json"),
        "last_feedback": values.get("last_feedback"),
        "turns": [t.model_dump(mode="json") for t in values.get("turns", [])],
    }


def from_snapshot(data: dict) -> dict:
    return {
        "config": InterviewConfig.model_validate(data["config"]),
        "ability": data["ability"],
        "difficulty": data["difficulty"],
        "main_question_count": data["main_question_count"],
        "follow_ups_used": data["follow_ups_used"],
        "current_question": Question.model_validate(data["current_question"]),
        "last_feedback": data.get("last_feedback"),
        "end_requested": False,
        "current_answer": "",
        "turns": [TurnRecord.model_validate(t) for t in data["turns"]],
    }


def question_payload(values: dict) -> dict:
    """What the UI needs to show the current question. Mirrors the payload built in nodes.await_answer."""
    q, cfg = values["current_question"], values["config"]
    return {
        "index": values["main_question_count"],
        "total": cfg.max_questions,
        "topic": q.topic,
        "difficulty": q.difficulty,
        "is_follow_up": q.is_follow_up,
        "text": q.text,
        "anchor": q.resume_anchor,
        "feedback": values.get("last_feedback") if cfg.practice_mode else None,
    }


def chat_items(values: dict) -> list[dict]:
    """The conversation so far, in the shape the chat screen renders (question, answer, feedback, ..., current question)."""
    cfg = values["config"]
    items: list[dict] = []

    def question_item(q) -> dict:
        return {"kind": "q", "text": q.text, "topic": q.topic, "difficulty": q.difficulty,
                "followUp": q.is_follow_up, "anchor": q.resume_anchor}

    for t in values.get("turns", []):
        items.append(question_item(t.question))
        items.append({"kind": "a", "text": t.answer})
        if cfg.practice_mode:
            items.append({"kind": "fb", "text": t.evaluation.feedback, "score": round(t.overall_score, 1),
                          "model": t.question.reference_answer or None})
    items.append(question_item(values["current_question"]))
    return items