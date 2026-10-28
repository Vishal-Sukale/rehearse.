from operator import add
from typing import Annotated, TypedDict

from .schemas import InterviewConfig, Question, Scorecard, TurnRecord


class InterviewState(TypedDict, total=False):
    """Everything the interview needs, checkpointed after every node.

    `turns` uses an append reducer so nodes return only the *new* turn.
    """
    config: InterviewConfig
    ability: float                 # running ability estimate (see difficulty.py)
    difficulty: int                # difficulty of the NEXT main question
    main_question_count: int
    follow_ups_used: int           # for the current main question
    current_question: Question | None
    current_answer: str
    last_feedback: str | None
    end_requested: bool
    turns: Annotated[list[TurnRecord], add]
    scorecard: Scorecard | None
