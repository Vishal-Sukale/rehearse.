"""Pure scoring helpers (no third-party imports, trivially unit-testable).

Numbers are computed deterministically in code. The LLM only produces
*judgements* (per-dimension 0-10 scores, feedback); it never does arithmetic
or decides the final hiring band.
"""

DIMENSION_WEIGHTS = {"correctness": 0.5, "depth": 0.3, "communication": 0.2}


def weighted_turn_score(correctness: float, depth: float, communication: float) -> float:
    """Blend the three rubric dimensions into one 0-10 score."""
    w = DIMENSION_WEIGHTS
    return (
        correctness * w["correctness"]
        + depth * w["depth"]
        + communication * w["communication"]
    )


def difficulty_weighted_mean(scores_and_difficulties: list[tuple[float, int]]) -> float:
    """Mean of 0-10 scores weighted by question difficulty (hard questions count more)."""
    if not scores_and_difficulties:
        return 0.0
    total_w = sum(d for _, d in scores_and_difficulties)
    return sum(s * d for s, d in scores_and_difficulties) / total_w


def hiring_band(score_out_of_100: float) -> str:
    if score_out_of_100 >= 80:
        return "strong_hire"
    if score_out_of_100 >= 65:
        return "hire"
    if score_out_of_100 >= 50:
        return "lean_hire"
    return "no_hire"


def grade_looks_suspicious(correctness: int, depth: int, covered: int, missed: int, misconceptions: int) -> bool:
    """Internal contradictions in a draft grade that justify a second-pass review ('fast' verification mode)."""
    return (
        (correctness >= 9 and missed > 0)
        or (correctness <= 3 and covered >= 2)
        or (correctness >= 7 and misconceptions > 0)
        or abs(correctness - depth) >= 5
    )


def parse_verify_mode(raw) -> str:
    """VERIFY_GRADING: 'fast' (default) | 'full' (always review) | 'off'. Legacy 1/0 still work."""
    mapping = {"0": "off", "false": "off", "off": "off", "no": "off", "1": "full", "true": "full", "full": "full", "fast": "fast"}
    return mapping.get(str(raw).strip().lower(), "fast")