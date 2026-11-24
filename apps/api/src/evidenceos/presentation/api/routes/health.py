"""Liveness is independent of the DB; readiness checks DB connectivity."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evidenceos.presentation.api.dependencies import get_db_session
from evidenceos.presentation.api.schemas import StatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=StatusResponse)
async def liveness() -> StatusResponse:
    return StatusResponse(status="alive")


@router.get("/ready", response_model=StatusResponse)
async def readiness(session: Annotated[AsyncSession, Depends(get_db_session)]) -> StatusResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - readiness intentionally masks DB internals
        # Never expose a connection URI, SQL parameters or driver diagnostics in logs.
        logger.warning("health.database_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from None
    return StatusResponse(status="ready")
