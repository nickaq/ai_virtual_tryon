"""In-memory rate limiter (development use)."""
import time
from typing import Dict, Tuple


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self._store: Dict[str, Tuple[int, float]] = {}  # key -> (count, reset_time)

    def check(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> dict:
        now = time.time()
        record = self._store.get(identifier)

        # No record or expired
        if record is None or now > record[1]:
            reset_time = now + window_seconds
            self._store[identifier] = (1, reset_time)
            return {
                "limited": False,
                "remaining": max_requests - 1,
                "resetAt": reset_time,
            }

        count, reset_time = record

        # Over limit
        if count >= max_requests:
            return {
                "limited": True,
                "remaining": 0,
                "resetAt": reset_time,
            }

        # Increment
        self._store[identifier] = (count + 1, reset_time)
        return {
            "limited": False,
            "remaining": max_requests - (count + 1),
            "resetAt": reset_time,
        }

    def cleanup(self):
        now = time.time()
        expired = [k for k, (_, rt) in self._store.items() if now > rt]
        for k in expired:
            del self._store[k]


# Global instance
rate_limiter = RateLimiter()
