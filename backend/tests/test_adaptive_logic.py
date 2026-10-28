"""Pure-Python tests (no pydantic/langgraph needed)."""
import unittest

from interviewer.difficulty import difficulty_from_ability, expected_performance, update_ability
from interviewer.planner import pick_topic
from interviewer.scoring import difficulty_weighted_mean, hiring_band, weighted_turn_score


class DifficultyTests(unittest.TestCase):
    def test_strong_answer_raises_difficulty(self):
        a = update_ability(2.5, 3, 9.0)
        self.assertGreater(a, 2.5)
        self.assertGreater(difficulty_from_ability(a), difficulty_from_ability(2.5))

    def test_weak_answer_lowers_ability(self):
        self.assertLess(update_ability(2.5, 3, 2.0), 2.5)

    def test_matching_expectation_is_stable(self):
        a = 3.0
        self.assertAlmostEqual(update_ability(a, 3, 10 * expected_performance(a, 3)), a)

    def test_beating_a_hard_question_moves_more_than_an_easy_one(self):
        gain_hard = update_ability(3.0, 5, 9.0) - 3.0
        gain_easy = update_ability(3.0, 1, 9.0) - 3.0
        self.assertGreater(gain_hard, gain_easy)

    def test_bounds(self):
        self.assertEqual(difficulty_from_ability(99), 5)
        self.assertEqual(difficulty_from_ability(-9), 1)
        self.assertLessEqual(update_ability(5.5, 5, 10), 5.5)
        self.assertGreaterEqual(update_ability(0.5, 1, 0), 0.5)

    def test_half_rounds_up_not_to_even(self):
        self.assertEqual(difficulty_from_ability(2.5), 3)

    def test_converges_for_consistently_strong_candidate(self):
        ability, d = 2.5, 3
        for _ in range(6):
            ability = update_ability(ability, d, 9.0)
            d = difficulty_from_ability(ability)
        self.assertEqual(d, 5)


class ScoringTests(unittest.TestCase):
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(weighted_turn_score(10, 10, 10), 10)

    def test_difficulty_weighting(self):
        # one 10 on a hard question + one 0 on an easy one beats the plain mean
        self.assertGreater(difficulty_weighted_mean([(10, 4), (0, 1)]), 5)

    def test_empty(self):
        self.assertEqual(difficulty_weighted_mean([]), 0.0)

    def test_bands(self):
        self.assertEqual(hiring_band(85), "strong_hire")
        self.assertEqual(hiring_band(70), "hire")
        self.assertEqual(hiring_band(55), "lean_hire")
        self.assertEqual(hiring_band(10), "no_hire")


class PlannerTests(unittest.TestCase):
    TOPICS = ["A", "B", "C"]

    def test_covers_unasked_topics_first(self):
        self.assertEqual(pick_topic(self.TOPICS, []), "A")
        self.assertEqual(pick_topic(self.TOPICS, [("A", 9)]), "B")

    def test_then_targets_weakest(self):
        hist = [("A", 9), ("B", 3), ("C", 7)]
        self.assertEqual(pick_topic(self.TOPICS, hist), "B")


if __name__ == "__main__":
    unittest.main()
