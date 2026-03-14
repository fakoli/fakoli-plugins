"""Token-bucket rate limiter with per-domain and global limits."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def try_consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitError(Exception):
    pass


class RateLimiter:
    def __init__(self):
        self._per_domain_rpm = int(os.environ.get("RATE_LIMIT_PER_DOMAIN", "10"))
        self._global_rpm = int(os.environ.get("RATE_LIMIT_GLOBAL", "60"))
        self._domain_buckets: dict[str, _Bucket] = {}
        self._global_bucket = _Bucket(
            capacity=self._global_rpm,
            refill_rate=self._global_rpm / 60.0,
        )

    def check(self, domain: str) -> None:
        if not self._global_bucket.try_consume():
            raise RateLimitError(
                f"Global rate limit exceeded ({self._global_rpm} req/min)"
            )

        if domain not in self._domain_buckets:
            self._domain_buckets[domain] = _Bucket(
                capacity=self._per_domain_rpm,
                refill_rate=self._per_domain_rpm / 60.0,
            )

        if not self._domain_buckets[domain].try_consume():
            raise RateLimitError(
                f"Per-domain rate limit exceeded for {domain} ({self._per_domain_rpm} req/min)"
            )
