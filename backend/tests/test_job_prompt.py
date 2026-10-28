import pytest

pytest.importorskip("pydantic")
from interviewer.prompts import JOB_RULES, build_question_prompt  # noqa: E402
from interviewer.schemas import InterviewConfig  # noqa: E402


def test_job_description_is_included_when_given():
    cfg = InterviewConfig(job_description="  Senior Backend Engineer at Acme. Kafka, Postgres.  ")
    text = build_question_prompt(cfg, "System design", 3, [], [])
    assert "<job_description>\nSenior Backend Engineer at Acme. Kafka, Postgres.\n</job_description>" in text
    assert JOB_RULES.strip()[:20] in text


def test_no_job_block_when_empty():
    assert "job_description" not in build_question_prompt(InterviewConfig(), "SQL", 2, [], [])


def test_overlong_job_description_is_rejected():
    with pytest.raises(ValueError):
        InterviewConfig(job_description="x" * 8001)