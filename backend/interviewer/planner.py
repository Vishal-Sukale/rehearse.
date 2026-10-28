"""Topic selection: cover every topic before repeating, then probe weak spots."""


def pick_topic(topics: list[str], history: list[tuple[str, float]]) -> str:
    """Choose the next topic.

    history: (topic, 0-10 score) for each *main* question asked so far.
    Ordering: fewest questions asked first, then lowest average score
    (dig into weaknesses), then the order the user listed the topics.
    """
    def key(item: tuple[int, str]):
        idx, topic = item
        scores = [s for t, s in history if t == topic]
        avg = sum(scores) / len(scores) if scores else 0.0
        return (len(scores), avg, idx)

    return min(enumerate(topics), key=key)[1]
