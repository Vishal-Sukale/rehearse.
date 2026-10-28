import contextlib
import io
import sys
import unittest

from interviewer.coding_kit import LANGUAGES, SAMPLE_PROBLEM, STARTERS, coding_score


def run_python_program(code, stdin_text):
    out, old = io.StringIO(), sys.stdin
    sys.stdin = io.StringIO(stdin_text)
    try:
        with contextlib.redirect_stdout(out):
            exec(code, {"__name__": "__main__"})
    finally:
        sys.stdin = old
    return out.getvalue().strip()


class CodingKitTests(unittest.TestCase):
    def test_score_is_70_percent_tests_and_30_percent_quality(self):
        self.assertEqual(coding_score(5, 6, 7), (8.3, 79))
        self.assertEqual(coding_score(0, 6, 10), (0.0, 30))
        self.assertEqual(coding_score(6, 6, 10), (10.0, 100))
        self.assertEqual(coding_score(9, 6, 15), (10.0, 100))   # out-of-range inputs are clamped

    def test_demo_problem_has_exactly_one_valid_answer_per_input(self):
        for text in SAMPLE_PROBLEM["test_inputs"]:
            lines = text.split("\n")
            nums, target = list(map(int, lines[1].split())), int(lines[2])
            pairs = [(i, j) for i in range(len(nums)) for j in range(i + 1, len(nums)) if nums[i] + nums[j] == target]
            self.assertEqual(len(pairs), 1)
            self.assertEqual(run_python_program(SAMPLE_PROBLEM["reference_solution"], text), "%d %d" % pairs[0])

    def test_every_language_has_a_starter_and_java_uses_class_main(self):
        self.assertEqual(set(LANGUAGES), set(STARTERS))
        self.assertIn("class Main", STARTERS["java"])
        self.assertEqual(LANGUAGES["java"]["filename"], "Main.java")


if __name__ == "__main__":
    unittest.main()