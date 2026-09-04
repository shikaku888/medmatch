from __future__ import annotations

import sqlite3

import pytest

from backend.rate_limit import RateLimitUnavailable, RateLimiter


def test_rate_limit_is_shared_between_limiter_instances(tmp_path) -> None:
    path = tmp_path / "rate-limit.db"
    first = RateLimiter(path)
    second = RateLimiter(path)

    assert first.allow("client:/api/scan", 1, 60) is True
    assert second.allow("client:/api/scan", 1, 60) is False

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM rate_limit_events").fetchone()[0] == 1


def test_rate_limit_store_failure_is_explicit(tmp_path) -> None:
    path = tmp_path / "not-a-directory" / "rate-limit.db"
    path.parent.write_text("file", encoding="utf-8")

    with pytest.raises(RateLimitUnavailable):
        RateLimiter(path).allow("client:/api/search", 1, 60)
