"""Progress numbers across a user's saved coding attempts. Pure Python."""
from collections import defaultdict


def coding_stats(rows: list[dict]) -> dict:
    """rows: dicts with id, created_at, score (0-100), passed, total, topic, language, title and seconds."""
    rows = sorted(rows, key=lambda r: r["created_at"])
    n = len(rows)
    if n == 0:
        return {"total": 0, "average": None, "best": None, "latest": None, "solved": 0, "solve_rate": 0,
                "avg_minutes": None, "trend": [], "topics": [], "languages": []}

    def group(key: str) -> list[dict]:
        buckets = defaultdict(list)
        for r in rows:
            buckets[r.get(key) or "Other"].append(r["score"])
        items = [{"name": k, "average": round(sum(v) / len(v), 1), "attempts": len(v)} for k, v in buckets.items()]
        return sorted(items, key=lambda i: (i["average"], i["name"]))   # weakest first

    scores = [r["score"] for r in rows]
    solved = sum(1 for r in rows if r["passed"] == r["total"])
    return {
        "total": n,
        "average": round(sum(scores) / n, 1),
        "best": max(scores),
        "latest": scores[-1],
        "solved": solved,
        "solve_rate": round(100 * solved / n),
        "avg_minutes": round(sum(r["seconds"] for r in rows) / n / 60, 1),
        "trend": [{"id": r["id"], "date": r["created_at"], "score": r["score"], "title": r["title"]} for r in rows[-30:]],
        "topics": group("topic"),
        "languages": group("language"),
    }