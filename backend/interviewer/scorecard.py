"""Deterministic scorecard assembly + rendering. The LLM adds only the narrative (FinalAnalysis)."""
from collections import defaultdict

from .schemas import InterviewConfig, Scorecard, TopicScore, TurnRecord
from .scoring import difficulty_weighted_mean, hiring_band


def build_scorecard(cfg: InterviewConfig, turns: list[TurnRecord], ability: float) -> Scorecard:
    n = len(turns)
    overall = difficulty_weighted_mean([(t.overall_score, t.question.difficulty) for t in turns]) * 10

    def avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    by_topic: dict[str, list[float]] = defaultdict(list)
    for t in turns:
        by_topic[t.question.topic].append(t.overall_score)

    passed = [t.question.difficulty for t in turns if t.overall_score >= 6]

    return Scorecard(
        role=cfg.role,
        seniority=cfg.seniority,
        questions_answered=n,
        overall_score=round(overall, 1),
        hiring_band=hiring_band(overall),
        dimension_averages={
            "correctness": avg([t.evaluation.correctness for t in turns]),
            "depth": avg([t.evaluation.depth for t in turns]),
            "communication": avg([t.evaluation.communication for t in turns]),
        },
        topic_breakdown=[
            TopicScore(topic=k, average_score=avg(v), questions=len(v)) for k, v in by_topic.items()
        ],
        difficulty_progression=[t.question.difficulty for t in turns if not t.question.is_follow_up],
        highest_difficulty_passed=max(passed, default=0),
        final_ability_estimate=round(ability, 2),
    )


def make_digest(card: Scorecard, turns: list[TurnRecord]) -> str:
    """Compact, factual summary handed to the LLM for the narrative analysis."""
    lines = [
        f"Overall: {card.overall_score}/100 ({card.hiring_band})",
        f"Dimension averages (0-10): {card.dimension_averages}",
        f"Difficulty progression: {card.difficulty_progression}; highest level passed: {card.highest_difficulty_passed}",
        "Topics: " + "; ".join(f"{t.topic}={t.average_score}/10" for t in card.topic_breakdown),
        "",
    ]
    for i, t in enumerate(turns, 1):
        e = t.evaluation
        tag = "follow-up" if t.question.is_follow_up else "main"
        lines += [
            f"[{i}] ({tag}, {t.question.topic}, difficulty {t.question.difficulty}) score {t.overall_score:.1f}/10",
            f"    Q: {t.question.text}",
            f"    covered: {e.covered_points}",
            f"    missed: {e.missed_points}",
            f"    misconceptions: {e.misconceptions}",
        ]
    return "\n".join(lines)


def _bar(value: float, maximum: float = 10, width: int = 20) -> str:
    filled = round(width * value / maximum)
    return "█" * filled + "░" * (width - filled)


def render_markdown(card: Scorecard) -> str:
    out = [
        f"# Interview Scorecard — {card.role} ({card.seniority.value})",
        "",
        f"**Overall: {card.overall_score}/100 — {card.hiring_band.replace('_', ' ').title()}**",
        f"Questions answered: {card.questions_answered} · "
        f"Highest difficulty passed: {card.highest_difficulty_passed}/5 · "
        f"Ability estimate: {card.final_ability_estimate}",
        "",
        "## Dimensions (0-10)",
    ]
    out += [f"- {k.title():<14} {_bar(v)} {v}" for k, v in card.dimension_averages.items()]
    out += ["", "## Topics (0-10)"]
    out += [f"- {t.topic:<32} {_bar(t.average_score)} {t.average_score} ({t.questions}q)" for t in card.topic_breakdown]
    out += ["", f"## Difficulty progression\n{' → '.join(map(str, card.difficulty_progression)) or '—'}"]
    if card.analysis:
        a = card.analysis
        out += ["", "## Summary", a.summary, "", "## Strengths"] + [f"- {s}" for s in a.strengths]
        out += ["", "## Areas to improve"] + [f"- {w}" for w in a.weaknesses]
        out += ["", "## Study plan"] + [f"{i}. {s}" for i, s in enumerate(a.study_plan, 1)]
    return "\n".join(out)
