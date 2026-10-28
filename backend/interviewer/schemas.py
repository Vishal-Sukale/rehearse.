"""Pydantic contracts for everything that crosses the LLM boundary or gets persisted.

Two kinds of models:
  * LLM-output schemas (GeneratedQuestion, AnswerEvaluation, FinalAnalysis) are passed to
    `llm.with_structured_output(...)`. Field descriptions double as prompt instructions.
  * Domain/record models (Question, TurnRecord, Scorecard) are what the state machine stores.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from .scoring import weighted_turn_score


class Seniority(str, Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"


Short = Annotated[str, StringConstraints(max_length=200, strip_whitespace=True)]
Medium = Annotated[str, StringConstraints(max_length=400, strip_whitespace=True)]


class ResumeExperience(BaseModel):
    company: Short = ""
    title: Short = ""
    highlights: list[Medium] = Field(
        default_factory=list, max_length=5,
        description="Concrete achievements or responsibilities, with numbers when the resume gives them.",
    )
    technologies: list[Short] = Field(default_factory=list, max_length=12)


class ResumeProject(BaseModel):
    name: Short = ""
    summary: Medium = ""
    technologies: list[Short] = Field(default_factory=list, max_length=12)


class ResumeProfile(BaseModel):
    """What we keep from a resume. Contact details (email, phone, address) are deliberately not extracted."""
    name: Short = ""
    headline: Medium = Field(default="", description="One-sentence summary of the candidate.")
    suggested_role: Short = Field(default="Software Engineer", description="Best-fit job title for interviews.")
    suggested_seniority: Seniority = Seniority.MID
    years_experience: float | None = Field(default=None, ge=0, le=50)
    skills: list[Short] = Field(
        default_factory=list, max_length=30,
        description="Technical skills, tools and languages, most important first.",
    )
    experience: list[ResumeExperience] = Field(default_factory=list, max_length=6)
    projects: list[ResumeProject] = Field(default_factory=list, max_length=5)
    education: list[Short] = Field(default_factory=list, max_length=3)


class InterviewConfig(BaseModel):
    role: str = "Backend Engineer"
    seniority: Seniority = Seniority.MID
    topics: list[str] = Field(
        default_factory=lambda: [
            "Data structures & algorithms",
            "System design",
            "Databases & storage",
            "Concurrency & performance",
        ],
        min_length=1,
    )
    max_questions: int = Field(5, ge=1, le=15, description="Main questions (follow-ups don't count).")
    max_follow_ups: int = Field(1, ge=0, le=2, description="Follow-up probes allowed per main question.")
    practice_mode: bool = Field(True, description="Show brief feedback after each answer.")
    resume: ResumeProfile | None = Field(None, description="If set, questions are grounded in this resume.")
    job_description: str = Field(
        "", max_length=8000, description="Optional job post. If set, questions are tailored to this job."
    )


# --------------------------------------------------------------------------- LLM outputs
class GeneratedQuestion(BaseModel):
    question: str = Field(description="The interview question, phrased as a interviewer would say it aloud.")
    reference_answer: str = Field(
        min_length=40,
        description="A concise, technically correct model answer (4-8 sentences). Private ground truth for grading.",
    )
    key_points: list[str] = Field(
        min_length=2,
        max_length=6,
        description="Concrete points a strong answer should cover. Used as a private grading reference.",
    )
    resume_anchor: str = Field(
        default="",
        description="If the question is grounded in the candidate's resume: a short label of the role, project or claim it refers to. Otherwise empty.",
    )


class AnswerEvaluation(BaseModel):
    reasoning: str = Field(
        description="Write this FIRST. Compare the answer to the reference point by point: what is correct, wrong and"
        " missing. Verify every technical claim before scoring."
    )
    correctness: int = Field(ge=0, le=10, description="Technical accuracy and completeness of the core answer.")
    depth: int = Field(ge=0, le=10, description="Trade-offs, edge cases, complexity, real-world awareness.")
    communication: int = Field(ge=0, le=10, description="Clarity, structure, and precise terminology.")
    covered_points: list[str] = Field(default_factory=list, description="Key points the candidate hit.")
    missed_points: list[str] = Field(default_factory=list, description="Key points the candidate missed.")
    misconceptions: list[str] = Field(default_factory=list, description="Factually wrong statements, if any.")
    feedback: str = Field(description="2-3 sentences of direct, constructive feedback addressed to the candidate.")
    needs_follow_up: bool = Field(
        description="True only if a targeted probe would reveal something the answer left ambiguous."
    )
    follow_up_question: str | None = Field(
        default=None, description="One focused probe. Required iff needs_follow_up is true."
    )

    @model_validator(mode="after")
    def _follow_up_consistency(self):
        if self.needs_follow_up and not (self.follow_up_question or "").strip():
            raise ValueError("follow_up_question is required when needs_follow_up is true")
        if not self.needs_follow_up:
            self.follow_up_question = None
        return self

    @model_validator(mode="after")
    def _scores_match_evidence(self):
        # Rejected outputs are retried with this message fed back to the model.
        if self.correctness >= 8 and not self.covered_points:
            raise ValueError("correctness >= 8 requires listing covered_points as evidence")
        if self.correctness >= 9 and self.misconceptions:
            raise ValueError("correctness >= 9 contradicts the listed misconceptions")
        if self.correctness <= 2 and len(self.covered_points) >= 3:
            raise ValueError("correctness <= 2 contradicts three or more covered points")
        return self


class FinalAnalysis(BaseModel):
    summary: str = Field(description="3-4 sentence overall assessment grounded in the evidence.")
    strengths: list[str] = Field(min_length=1, max_length=5)
    weaknesses: list[str] = Field(max_length=5)
    study_plan: list[str] = Field(
        min_length=1, max_length=6, description="Specific, actionable topics/exercises ordered by priority."
    )


class QuestionCheck(BaseModel):
    is_correct: bool = Field(
        description="True if the reference answer and key points are technically accurate and complete."
    )
    issues: list[str] = Field(default_factory=list, description="Factual errors or gaps found.")
    corrected_reference_answer: str | None = Field(
        default=None, description="A fixed reference answer. Required when is_correct is false."
    )

    @model_validator(mode="after")
    def _needs_fix(self):
        if not self.is_correct and not (self.corrected_reference_answer or "").strip():
            raise ValueError("corrected_reference_answer is required when is_correct is false")
        return self


# --------------------------------------------------------------------------- domain records
class Question(BaseModel):
    text: str
    topic: str
    difficulty: int = Field(ge=1, le=5)
    key_points: list[str] = Field(default_factory=list)
    reference_answer: str = ""
    resume_anchor: str = ""
    is_follow_up: bool = False


class TurnRecord(BaseModel):
    question: Question
    answer: str
    evaluation: AnswerEvaluation
    answered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def overall_score(self) -> float:
        e = self.evaluation
        return weighted_turn_score(e.correctness, e.depth, e.communication)


class TopicScore(BaseModel):
    topic: str
    average_score: float = Field(description="0-10")
    questions: int


class Scorecard(BaseModel):
    role: str
    seniority: Seniority
    questions_answered: int
    overall_score: float = Field(ge=0, le=100, description="Difficulty-weighted, 0-100.")
    hiring_band: Literal["strong_hire", "hire", "lean_hire", "no_hire"]
    dimension_averages: dict[str, float]
    topic_breakdown: list[TopicScore]
    difficulty_progression: list[int] = Field(description="Difficulty of each main question, in order.")
    highest_difficulty_passed: int = Field(description="Hardest level where the candidate scored >= 6/10 (0 if none).")
    final_ability_estimate: float
    analysis: FinalAnalysis | None = None