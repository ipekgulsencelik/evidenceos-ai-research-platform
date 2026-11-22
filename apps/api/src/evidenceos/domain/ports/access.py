"""Ports for project memberships and append-only access-decision audit history."""

from typing import Protocol
from uuid import UUID

from evidenceos.domain.entities.access import (
    AccessDecisionEvent,
    ProjectMembership,
    ProjectRole,
)


class MembershipRepository(Protocol):
    async def role_for(self, project_id: UUID, principal_key: str) -> ProjectRole | None: ...

    async def upsert(self, membership: ProjectMembership) -> None: ...

    async def project_ids_for(self, principal_key: str, *, limit: int = 50) -> list[UUID]: ...


class AccessAuditRepository(Protocol):
    async def append(self, event: AccessDecisionEvent) -> None: ...

    async def latest(self, project_id: UUID, *, limit: int = 100) -> list[AccessDecisionEvent]: ...
