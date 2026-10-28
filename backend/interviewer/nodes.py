"""Graph nodes. Each node is a small function: read state -> return a partial state update."""
import os
import re
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

from langgraph.types import interrupt
from pydantic import BaseModel

from . import prompts
from .difficulty import START_ABILITY, difficulty_from_ability, update_ability
from .planner import pick_topic
from .schemas import (
    AnswerEvaluation, FinalAnalysis, GeneratedQuestion, Question, QuestionCheck, TurnRecord,
)
from .scorecard import build_scorecard, make_digest
from .scoring import grade_looks_suspicious, parse_verify_mode
from .state import InterviewState

T = TypeVar("T", bound=BaseModel)

END_COMMAND = "/end"
MAX_LLM_ATTEMPTS = 3
NON_ANSWERS = {"i dont know", "i don't know", "idk", "no idea", "not sure", "skip", "pass"}


def is_non_answer(answer: str) -> bool:
    """Deterministic guard: blank / 'I don't know' never reaches the LLM grader, so it can't be graded generously."""
    cleaned = re.sub(r"[^a-z' ]", "", answer.lower()).strip()
    return not cleaned or cleaned in NON_ANSWERS or (
        len(cleaned.split()) <= 6 and cleaned.startswith(("i dont know", "i don't know", "no idea", "idk"))
    )


class InterviewNodes:
    def __init__(self, llm, verify: str | bool | None = None):
        self.llm = llm
        raw = os.getenv("VERIFY_GRADING") if verify is None else verify
        # "fast" (default): fact-check in the background + review only suspicious grades.
        # "full": always review every grade.  "off": single grading pass, no checks.
        self.mode = {True: "full", False: "off"}.get(raw) or parse_verify_mode(raw)
        self._pool = ThreadPoolExecutor(max_workers=4)
        self._checks: dict[str, Future] = {}   # question text -> pending fact-check of its reference answer

    # ------------------------------------------------------------------ LLM helper
    def _structured(self, schema: type[T], system: str, user: str) -> T:
        """Structured extraction with a self-correction loop.

        If the model returns something that fails Pydantic validation, we feed the validation
        error back and retry instead of crashing the interview.
        """
        runnable = self.llm.with_structured_output(schema)
        messages = [("system", system), ("human", user)]
        last_err: Exception | None = None
        for _ in range(MAX_LLM_ATTEMPTS):
            try:
                result = runnable.invoke(messages)
                return result if isinstance(result, schema) else schema.model_validate(result)
            except Exception as err:  # noqa: BLE001 - parser/validation/transport errors all retry
                last_err = err
                messages = messages + [
                    ("human", f"Your previous output was invalid: {err}\nReturn a corrected response.")
                ]
        raise RuntimeError(f"LLM failed to produce valid {schema.__name__}") from last_err

    def _fact_check(self, out: GeneratedQuestion) -> str:
        """Returns a verified reference answer. Never raises: a failed check just keeps the original."""
        try:
            check = self._structured(
                QuestionCheck, prompts.CHECK_SYSTEM,
                prompts.build_check_prompt(out.question, out.reference_answer, out.key_points),
            )
            return out.reference_answer if check.is_correct else check.corrected_reference_answer
        except Exception:  # noqa: BLE001
            return out.reference_answer

    def _resolve_reference(self, q: Question) -> Question:
        """Collect the background fact-check (it has had the whole time the candidate spent answering)."""
        future = self._checks.pop(q.text, None)
        if future is None:
            return q
        try:
            return q.model_copy(update={"reference_answer": future.result(timeout=45)})
        except Exception:  # noqa: BLE001
            return q

    # ------------------------------------------------------------------ nodes
    def setup(self, state: InterviewState) -> dict:
        ability = START_ABILITY[state["config"].seniority.value]
        return {
            "ability": ability,
            "difficulty": difficulty_from_ability(ability),
            "main_question_count": 0,
            "follow_ups_used": 0,
            "end_requested": False,
            "last_feedback": None,
        }

    def generate_question(self, state: InterviewState) -> dict:
        cfg = state["config"]
        turns = state.get("turns", [])
        main = [t for t in turns if not t.question.is_follow_up]

        topic = pick_topic(cfg.topics, [(t.question.topic, t.overall_score) for t in main])
        weak = [p for t in turns if t.question.topic == topic for p in t.evaluation.missed_points][-4:]
        difficulty = state["difficulty"]

        resume_text = prompts.resume_digest(cfg.resume) if cfg.resume else ""
        system = prompts.QUESTION_SYSTEM + (prompts.RESUME_QUESTION_RULES if cfg.resume else "")
        out = self._structured(
            GeneratedQuestion,
            system,
            prompts.build_question_prompt(cfg, topic, difficulty, [t.question.text for t in main], weak, resume_text),
        )
        # Fact-check the reference answer in the background while the candidate reads and answers,
        # so it adds no waiting time. evaluate_answer collects the result before grading.
        if self.mode != "off":
            self._checks[out.question] = self._pool.submit(self._fact_check, out)

        question = Question(
            text=out.question,
            topic=topic,
            difficulty=difficulty,   # set by the state machine, never trusted from the LLM
            key_points=out.key_points,
            reference_answer=out.reference_answer,
            resume_anchor=out.resume_anchor,
        )
        return {
            "current_question": question,
            "main_question_count": state["main_question_count"] + 1,
            "follow_ups_used": 0,
        }

    def await_answer(self, state: InterviewState) -> dict:
        """Pause the graph until the human answers (human-in-the-loop via interrupt)."""
        q = state["current_question"]
        cfg = state["config"]
        answer = interrupt(
            {
                "index": state["main_question_count"],
                "total": cfg.max_questions,
                "topic": q.topic,
                "difficulty": q.difficulty,
                "is_follow_up": q.is_follow_up,
                "text": q.text,
                "anchor": q.resume_anchor,
                "feedback": state.get("last_feedback") if cfg.practice_mode else None,
            }
        )
        if str(answer).strip().lower() == END_COMMAND:
            return {"end_requested": True, "current_answer": ""}
        return {"current_answer": str(answer)}

    def evaluate_answer(self, state: InterviewState) -> dict:
        cfg = state["config"]
        q = self._resolve_reference(state["current_question"])   # picks up the background fact-check
        answer = state["current_answer"]
        if is_non_answer(answer):
            evaluation = AnswerEvaluation(
                reasoning="No substantive answer was given.",
                correctness=0, depth=0, communication=1,
                missed_points=q.key_points,
                feedback="You didn't attempt this one. Even a partial approach helps: say what you'd try first and where you'd get stuck.",
                needs_follow_up=False,
            )
        else:
            evaluation = self._structured(
                AnswerEvaluation, prompts.EVAL_SYSTEM, prompts.build_evaluation_prompt(cfg, q, answer)
            )
            suspicious = grade_looks_suspicious(
                evaluation.correctness, evaluation.depth,
                len(evaluation.covered_points), len(evaluation.missed_points), len(evaluation.misconceptions),
            )
            if self.mode == "full" or (self.mode == "fast" and suspicious):
                evaluation = self._structured(
                    AnswerEvaluation,
                    prompts.VERIFY_SYSTEM,
                    prompts.build_verify_prompt(cfg, q, answer, evaluation),
                )
        return {
            "turns": [TurnRecord(question=q, answer=answer, evaluation=evaluation)],
            "last_feedback": evaluation.feedback,
        }

    def adapt_difficulty(self, state: InterviewState) -> dict:
        last = state["turns"][-1]
        ability = update_ability(state["ability"], last.question.difficulty, last.overall_score)
        return {"ability": ability, "difficulty": difficulty_from_ability(ability)}

    def ask_follow_up(self, state: InterviewState) -> dict:
        prev = state["current_question"]
        ev = state["turns"][-1].evaluation
        follow_up = Question(
            text=ev.follow_up_question,
            topic=prev.topic,
            difficulty=prev.difficulty,       # probe stays at the level of the original question
            key_points=ev.missed_points,
            resume_anchor=prev.resume_anchor,
            is_follow_up=True,
        )
        return {"current_question": follow_up, "follow_ups_used": state["follow_ups_used"] + 1}

    def final_report(self, state: InterviewState) -> dict:
        cfg, turns = state["config"], state.get("turns", [])
        card = build_scorecard(cfg, turns, state["ability"])
        if turns:
            analysis = self._structured(
                FinalAnalysis, prompts.ANALYSIS_SYSTEM, prompts.build_analysis_prompt(cfg, make_digest(card, turns))
            )
            card = card.model_copy(update={"analysis": analysis})
        return {"scorecard": card}


# ---------------------------------------------------------------------- routing
def route_after_answer(state: InterviewState) -> str:
    return "final_report" if state.get("end_requested") else "evaluate_answer"


def route_after_adapt(state: InterviewState) -> str:
    cfg = state["config"]
    ev = state["turns"][-1].evaluation
    if ev.needs_follow_up and state["follow_ups_used"] < cfg.max_follow_ups:
        return "ask_follow_up"
    if state["main_question_count"] >= cfg.max_questions:
        return "final_report"
    return "generate_question"