"""Grading-quality check: runs labeled answers through the REAL grader and verifies the scores land in the expected range.

Run it whenever you change a prompt, the model, or the scoring rules:
    cd backend
    python -m evals.run_evals            # one pass
    python -m evals.run_evals --repeat 3 # three passes per case (also shows how stable the grader is)

Needs a real model (GROQ_API_KEY or another provider in .env). Exit code 1 if any case is out of range.
"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from interviewer import prompts  # noqa: E402
from interviewer.llm import get_llm  # noqa: E402
from interviewer.nodes import InterviewNodes  # noqa: E402
from interviewer.schemas import AnswerEvaluation, InterviewConfig, Question  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Check grading quality against labeled answers")
    parser.add_argument("--repeat", type=int, default=1, help="grade each case this many times")
    args = parser.parse_args()

    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    nodes = InterviewNodes(get_llm(), verify="off")   # grade once, so we measure the grader itself
    cfg = InterviewConfig()
    failures = 0

    for case in cases:
        question = Question(
            text=case["question"], topic=case["topic"], difficulty=case.get("difficulty", 3),
            key_points=case["key_points"], reference_answer=case["reference"],
        )
        scores = []
        for _ in range(args.repeat):
            evaluation = nodes._structured(
                AnswerEvaluation, prompts.EVAL_SYSTEM, prompts.build_evaluation_prompt(cfg, question, case["answer"])
            )
            scores.append(evaluation.correctness)
        low, high = case["expect_correctness"]
        ok = all(low <= s <= high for s in scores)
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {case['id']:<32} correctness={scores} expected {low}-{high}")

    print(f"\n{len(cases) - failures}/{len(cases)} cases in range")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()