"""Progress analytics across a user's saved interviews. Pure Python, no third-party imports."""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone


def compute_stats(rows: list[dict], today=None) -> dict:
    """rows: dicts with created_at (unix seconds), overall_score, role, id and scorecard_json (a JSON string)."""
    rows = sorted(rows, key=lambda r: r["created_at"])
    scores = [float(r["overall_score"]) for r in rows]

    topic_sum, topic_n = defaultdict(float), defaultdict(int)
    dim_sum, dim_cards = defaultdict(float), 0
    for r in rows:
        try:
            card = json.loads(r.get("scorecard_json") or "{}")
        except ValueError:
            card = {}
        for t in card.get("topic_breakdown", []):
            q = max(int(t.get("questions", 1)), 1)
            topic_sum[t["topic"]] += float(t["average_score"]) * q    # weight by number of questions
            topic_n[t["topic"]] += q
        dims = card.get("dimension_averages") or {}
        if dims:
            dim_cards += 1
            for k, v in dims.items():
                dim_sum[k] += float(v)

    topics = sorted(
        ({"topic": k, "score": round(topic_sum[k] / topic_n[k], 1), "questions": topic_n[k]} for k in topic_sum),
        key=lambda t: t["score"],   # weakest first
    )

    days = {datetime.fromtimestamp(r["created_at"], tz=timezone.utc).date() for r in rows}
    today = today or datetime.now(timezone.utc).date()
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)

    return {
        "total": len(rows),
        "average": round(sum(scores) / len(scores), 1) if scores else None,
        "best": round(max(scores), 1) if scores else None,
        "latest": round(scores[-1], 1) if scores else None,
        "change_since_first": round(scores[-1] - scores[0], 1) if len(scores) >= 2 else None,
        "streak_days": streak,
        "trend": [
            {"id": r["id"], "date": r["created_at"], "score": round(float(r["overall_score"]), 1), "role": r.get("role", "")}
            for r in rows
        ],
        "topics": topics,
        "dimensions": {k: round(v / dim_cards, 1) for k, v in dim_sum.items()} if dim_cards else {},
    }