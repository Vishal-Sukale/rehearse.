"""CLI runner:  python main.py --role "Backend Engineer" --seniority mid --questions 5
Offline demo (no API key): python main.py --offline"""
import argparse
import uuid
from pathlib import Path

from langgraph.types import Command

from interviewer.graph import build_graph
from interviewer.schemas import InterviewConfig, Seniority
from interviewer.scorecard import render_markdown
from dotenv import load_dotenv
from langgraph.types import Command

def parse_args():
    p = argparse.ArgumentParser(description="Agentic mock technical interviewer")
    p.add_argument("--role", default="Backend Engineer")
    p.add_argument("--seniority", choices=[s.value for s in Seniority], default="mid")
    p.add_argument("--topics", default=None, help="Comma-separated topics")
    p.add_argument("--questions", type=int, default=5)
    p.add_argument("--no-feedback", action="store_true", help="Strict mode: hide per-answer feedback")
    p.add_argument("--model", default=None, help='e.g. "anthropic:claude-sonnet-5-5"')
    p.add_argument("--offline", action="store_true", help="Use a fake LLM (no API key needed)")
    p.add_argument("--out", default="reports", help="Directory for the JSON scorecard")
    return p.parse_args()


def main():
    args = parse_args()

    if args.offline:
        from interviewer.testing import FakeLLM
        llm = FakeLLM()
    else:
        from interviewer.llm import get_llm
        llm = get_llm(args.model)

    cfg_kwargs = dict(
        role=args.role,
        seniority=args.seniority,
        max_questions=args.questions,
        practice_mode=not args.no_feedback,
    )
    if args.topics:
        cfg_kwargs["topics"] = [t.strip() for t in args.topics.split(",") if t.strip()]
    cfg = InterviewConfig(**cfg_kwargs)

    graph = build_graph(llm)
    run = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 100}

    print(f"\nMock interview: {cfg.role} ({cfg.seniority.value}) · {cfg.max_questions} questions")
    print("Type your answer and press Enter. Type /end to finish early.\n")

    result = graph.invoke({"config": cfg}, run)
    while "__interrupt__" in result:
        q = result["__interrupt__"][0].value
        if q.get("feedback"):
            print(f"  ↳ Feedback: {q['feedback']}\n")
        label = "Follow-up" if q["is_follow_up"] else f"Q{q['index']}/{q['total']}"
        print(f"[{label} · {q['topic']} · difficulty {q['difficulty']}/5]\n{q['text']}")
        answer = input("\n> ")
        print()
        result = graph.invoke(Command(resume=answer), run)

    card = result["scorecard"]
    print("=" * 60 + "\n" + render_markdown(card))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"scorecard_{run['configurable']['thread_id'][:8]}.json"
    path.write_text(card.model_dump_json(indent=2))
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
