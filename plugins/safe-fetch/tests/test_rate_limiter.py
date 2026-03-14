"""Tests for rate limiting."""

from __future__ import annotations

import pytest

from safe_fetch.rate_limiter import RateLimiter, RateLimitError


class TestRateLimiter:
    def test_allows_initial_requests(self):
        limiter = RateLimiter()
        # Should not raise for first few requests
        for _ in range(5):
            limiter.check("example.com")

    def test_per_domain_limit(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_DOMAIN", "3")
        monkeypatch.setenv("RATE_LIMIT_GLOBAL", "100")
        limiter = RateLimiter()

        for _ in range(3):
            limiter.check("test.com")

        with pytest.raises(RateLimitError, match="Per-domain"):
            limiter.check("test.com")

    def test_different_domains_independent(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_DOMAIN", "2")
        monkeypatch.setenv("RATE_LIMIT_GLOBAL", "100")
        limiter = RateLimiter()

        limiter.check("a.com")
        limiter.check("a.com")
        # a.com is exhausted, but b.com should be fine
        limiter.check("b.com")

    def test_global_limit(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_DOMAIN", "100")
        monkeypatch.setenv("RATE_LIMIT_GLOBAL", "5")
        limiter = RateLimiter()

        for i in range(5):
            limiter.check(f"domain{i}.com")

        with pytest.raises(RateLimitError, match="Global"):
            limiter.check("another.com")
