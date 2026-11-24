"""Atomic fixed-window quotas across two real Redis client instances."""

import asyncio
import os
from uuid import uuid4

import pytest

from evidenceos.infrastructure.redis_rate_limits import RedisApiRateLimiter


@pytest.mark.integration
async def test_shared_redis_rate_budget_is_atomic_across_replicas() -> None:
    url = os.getenv("EVIDENCEOS_RATE_LIMIT_TEST_URL")
    password = os.getenv("EVIDENCEOS_RATE_LIMIT_TEST_PASSWORD")
    if not url or not password:
        pytest.skip("disposable authenticated Redis required")
    left = RedisApiRateLimiter(url, password)
    right = RedisApiRateLimiter(url, password)
    try:
        principal = uuid4().hex
        decisions = await asyncio.gather(
            *[
                (left if i % 2 else right).consume(
                    principal, maximum=3, expensive_maximum=1, expensive=False
                )
                for i in range(20)
            ]
        )
        assert sum(decision.allowed for decision in decisions) == 3
        assert all(d.retry_after_seconds >= 1 for d in decisions if not d.allowed)

        # Expensive tasks have a narrower quota, but cheap requests retain
        # the remaining global quota. Both decisions are atomic in Redis.
        another_principal = uuid4().hex
        first = await left.consume(
            another_principal, maximum=3, expensive_maximum=1, expensive=True
        )
        second = await right.consume(
            another_principal, maximum=3, expensive_maximum=1, expensive=True
        )
        third = await left.consume(
            another_principal, maximum=3, expensive_maximum=1, expensive=False
        )
        assert first.allowed is True
        assert second.allowed is False
        assert second.retry_after_seconds > 0
        assert third.allowed is True
    finally:
        await left.aclose()
        await right.aclose()
