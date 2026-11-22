"""Privileged read-only access-decision history for a research project."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, status
from pydantic import BaseModel, ConfigDict

from evidenceos.application.use_cases.access import ManageProjectMemberships
from evidenceos.domain.entities.access import (
    AccessDecisionEvent,
    Principal,
    ProjectMembership,
    ProjectRole,
)
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.security import validate_service_credential

router = APIRouter(prefix="/projects/{project_id}", tags=["project access audit"])
identity_router = APIRouter(tags=["identity"])


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


class VerifiedIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_key: str
    kind: str


@identity_router.get("/identity", response_model=VerifiedIdentityResponse)
async def my_verified_identity(
    actor: Annotated[Principal, Depends(validate_service_credential)],
) -> VerifiedIdentityResponse:
    """Never infer a member from an email, header or unverified client claim."""
    return VerifiedIdentityResponse(principal_key=actor.key, kind=actor.kind)


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_key: str
    role: ProjectRole
    created_at: datetime

    @classmethod
    def from_entity(cls, row: ProjectMembership) -> "ProjectMemberResponse":
        return cls(
            principal_key=row.principal_key,
            role=row.role,
            created_at=row.created_at,
        )


class ProjectMemberRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: ProjectRole


MemberKey = Annotated[str, Path(pattern=r"^[a-f0-9]{64}$", min_length=64, max_length=64)]


@router.get("/memberships", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: UUID,
    request: Request,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    actor: Annotated[Principal, Depends(validate_service_credential)],
) -> list[ProjectMemberResponse]:
    entries = await ManageProjectMemberships(factory).list_members(
        actor, project_id, getattr(request.state, "request_id", "")
    )
    return [ProjectMemberResponse.from_entity(row) for row in entries]


@router.put("/memberships/{member_key}", response_model=ProjectMemberResponse)
async def assign_project_member(
    project_id: UUID,
    member_key: MemberKey,
    payload: ProjectMemberRoleRequest,
    request: Request,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    actor: Annotated[Principal, Depends(validate_service_credential)],
) -> ProjectMemberResponse:
    member = await ManageProjectMemberships(factory).assign(
        actor,
        project_id,
        member_key,
        payload.role,
        getattr(request.state, "request_id", ""),
    )
    return ProjectMemberResponse.from_entity(member)


@router.delete("/memberships/{member_key}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_project_member(
    project_id: UUID,
    member_key: MemberKey,
    request: Request,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    actor: Annotated[Principal, Depends(validate_service_credential)],
) -> None:
    await ManageProjectMemberships(factory).revoke(
        actor, project_id, member_key, getattr(request.state, "request_id", "")
    )
