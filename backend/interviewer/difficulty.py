"""Adaptive difficulty engine.

An Elo / item-response-style ability estimate:

    expected = sigmoid(ability - difficulty)     # P(strong answer)
    ability += K * (actual - expected)           # actual = score / 10

Beating expectations at a given level pushes ability (and thus the next
question's difficulty) up; underperforming pulls it down. The size of the move
depends on how surprising the result was, so a 9/10 on an easy question moves
you less than a 9/10 on a hard one.
"""
import math

MIN_DIFFICULTY, MAX_DIFFICULTY = 1, 5
MIN_ABILITY, MAX_ABILITY = 0.5, 5.5
K_FACTOR = 2.0

START_ABILITY = {"junior": 1.5, "mid": 2.5, "senior": 3.5, "staff": 4.0}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def expected_performance(ability: float, difficulty: int) -> float:
    return _sigmoid(ability - difficulty)


def update_ability(ability: float, difficulty: int, score_out_of_10: float, k: float = K_FACTOR) -> float:
    actual = max(0.0, min(10.0, score_out_of_10)) / 10.0
    new = ability + k * (actual - expected_performance(ability, difficulty))
    return max(MIN_ABILITY, min(MAX_ABILITY, new))


def difficulty_from_ability(ability: float) -> int:
    # floor(x + 0.5) rather than round(): Python's round() is banker's rounding
    rounded = int(math.floor(ability + 0.5))
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, rounded))
