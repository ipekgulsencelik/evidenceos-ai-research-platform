"""Authenticated API rate limits; untrusted client-supplied identity is ignored."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from evidenceos.domain.entities.access import Principal
from evidenceos.domain.ports.rate_limits import RateLimitStore
from evidenceos.infrastructure.config import Settings
from evidenceos.presentation.api.security import validate_service_credential

logger = logging.getLogger(__name__)

# High-cost routes warrant a separate tighter quota, in addition to the
# per-principal total-request quota. Keep health probes unmetered.
HIGH_COST_SUFFIXES = (
    "/evidence/assess",
    "/documents/retrieve-passages",
    "/literature/analyze-pdf",
    "/semantic-gaps",
    "/methodology-review",
)


def is_high_cost_request(method: str, path: str) -> bool:
    return method in {"POST", "PUT"} and path.endswith(HIGH_COST_SUFFIXES)


async def enforce_research_rate_limit(
    request: Request,
    principal: Annotated[Principal, Depends(validate_service_credential)],
) -> None:
    settings: Settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    store: RateLimitStore = request.app.state.rate_limiter
    try:
        result = await store.consume(
            principal.key,
            maximum=settings.rate_limit_requests_per_minute,
            expensive_maximum=settings.rate_limit_expensive_per_minute,
            expensive=is_high_cost_request(request.method, request.url.path),
        )
    except Exception:  # noqa: BLE001 - storage errors must fail closed
        logger.error(
            "security.rate_limit_unavailable request_id=%s",
            getattr(request.state, "request_id", "unknown"),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting temporarily unavailable",
            headers={"Retry-After": "5", "Cache-Control": "no-store"},
        ) from None
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={
                "Retry-After": str(max(1, result.retry_after_seconds)),
                "Cache-Control": "no-store",
            },
        )
