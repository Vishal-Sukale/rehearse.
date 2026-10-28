"""End-to-end graph tests using FakeLLM. Requires: pip install -r requirements.txt"""
import pytest

pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from langgraph.types import Command  # noqa: E402

from interviewer.graph import build_graph  # noqa: E402
from interviewer.schemas import AnswerEvaluation, InterviewConfig  # noqa: E402
from interviewer.testing import FakeLLM  # noqa: E402

STRONG = " ".join(["word"] * 50)      # FakeLLM -> 9/10
MEDIOCRE = " ".join(["word"] * 20)    # FakeLLM -> 6/10, triggers a follow-up
WEAK = "no idea"                      # FakeLLM -> 2/10


def run_interview(answers, **cfg_kwargs):
    cfg = InterviewConfig(topics=["Algo", "Design"], **cfg_kwargs)
    graph = build_graph(FakeLLM())
    run = {"configurable": {"thread_id": "t"}, "recursion_limit": 100}
    result = graph.invoke({"config": cfg}, run)
    asked, it = [], iter(answers)
    while "__interrupt__" in result:
        asked.append(result["__interrupt__"][0].value)
        result = graph.invoke(Command(resume=next(it)), run)
    return result, asked


def test_difficulty_rises_on_strong_answers():
    result, asked = run_interview([STRONG] * 4, seniority="mid", max_questions=4)
    levels = result["scorecard"].difficulty_progression
    assert levels == sorted(levels) and levels[-1] > levels[0]


def test_difficulty_falls_on_weak_answers():
    result, _ = run_interview([WEAK] * 4, seniority="mid", max_questions=4)
    levels = result["scorecard"].difficulty_progression
    assert levels[-1] < levels[0]


def test_follow_up_is_asked_once_and_not_counted_as_main_question():
    result, asked = run_interview([MEDIOCRE, STRONG, STRONG], max_questions=2, max_follow_ups=1)
    assert [q["is_follow_up"] for q in asked][:2] == [False, True]
    assert len(result["scorecard"].difficulty_progression) == 2


def test_end_command_produces_scorecard_early():
    result, asked = run_interview([STRONG, "/end"], max_questions=5)
    assert result["scorecard"].questions_answered == 1


def test_end_before_any_answer_is_safe():
    result, _ = run_interview(["/end"], max_questions=3)
    card = result["scorecard"]
    assert card.questions_answered == 0 and card.analysis is None


def test_scorecard_is_valid_and_serializable():
    result, _ = run_interview([STRONG] * 2, max_questions=2)
    card = result["scorecard"]
    assert 0 <= card.overall_score <= 100
    assert card.analysis is not None
    assert type(card).model_validate_json(card.model_dump_json()) == card


def test_evaluation_schema_rejects_follow_up_without_question():
    with pytest.raises(ValueError):
        AnswerEvaluation(correctness=5, depth=5, communication=5, feedback="x", needs_follow_up=True)
