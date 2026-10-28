"""Tiny in-memory sliding-window rate limiter (per process).

Fine for a single server. If you run several instances, move this to Redis or an API gateway.
"""
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """Record an attempt for `key`. False means the caller is over the limit."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:   # keep memory bounded
                for k in [k for k, q in self._hits.items() if not q or now - q[-1] > self.window]:
                    del self._hits[k]
            return True