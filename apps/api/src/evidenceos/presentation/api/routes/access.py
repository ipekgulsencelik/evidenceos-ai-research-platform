"""Privileged read-only access-decision history for a research project."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from evidenceos.domain.entities.access import AccessDecisionEvent
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.presentation.api.dependencies import get_uow_factory

router = APIRouter(prefix="/projects/{project_id}", tags=["project access audit"])


class AccessDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    actor_key: str
    project_id: UUID | None
    action: str
    outcome: str
    request_id: str
    created_at: datetime

    @classmethod
    def from_event(cls, event: AccessDecisionEvent) -> "AccessDecisionResponse":
        return cls(
            id=event.id,
            actor_key=event.actor_key,
            project_id=event.project_id,
            action=event.action,
            outcome=event.outcome,
            request_id=event.request_id,
            created_at=event.created_at,
        )


@router.get("/access-audit", response_model=list[AccessDecisionResponse])
async def access_decisions(
    project_id: UUID,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[AccessDecisionResponse]:
    async with factory() as uow:
        rows = await uow.access_audit.latest(project_id, limit=limit)
    return [AccessDecisionResponse.from_event(row) for row in rows]
