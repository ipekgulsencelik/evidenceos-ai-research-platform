"""Storage-independent, authenticated research API admission policy."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class RateLimitStore(Protocol):
    """A shared atomic store; multiple API replicas must agree on each budget."""

    async def consume(
        self,
        principal_key: str,
        *,
        maximum: int,
        expensive_maximum: int,
        expensive: bool,
    ) -> RateLimitDecision: ...

    async def aclose(self) -> None: ...
