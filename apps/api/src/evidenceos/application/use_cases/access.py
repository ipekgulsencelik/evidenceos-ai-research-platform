"""Authorization decisions depend on domain ports, not web frameworks or SQLAlchemy."""

from uuid import UUID

from evidenceos.domain.entities.access import (
    AccessDecisionEvent,
    Principal,
    ProjectAction,
    ProjectMembership,
    ProjectRole,
    role_allows,
)
from evidenceos.domain.errors import InvalidMembershipChange, ProjectNotFound
from evidenceos.domain.ports.repositories import UnitOfWork, UnitOfWorkFactory


class EnforceProjectAccess:
    def __init__(self, factory: UnitOfWorkFactory) -> None:
        self._factory = factory

    async def execute(
        self, actor: Principal, project_id: UUID, action: ProjectAction, request_id: str = ""
    ) -> None:
        async with self._factory() as uow:
            role = (
                None if actor.is_operator else await uow.memberships.role_for(project_id, actor.key)
            )
            allowed = actor.is_operator or role_allows(role, action)
            # Only writes and denials are journalled to keep read traffic bounded.
            if action is not ProjectAction.READ or not allowed:
                await uow.access_audit.append(
                    AccessDecisionEvent.create(
                        actor.key,
                        project_id,
                        action.value,
                        "allowed" if allowed else "denied",
                        request_id,
                    )
                )
                await uow.commit()
        if not allowed:
            # Use 404 for unauthorised project IDs to avoid enumerating private projects.
            raise ProjectNotFound(f"project '{project_id}' not found")


class AssignProjectRole:
    """Trusted application command; no externally callable grant route until OIDC."""

    def __init__(self, factory: UnitOfWorkFactory) -> None:
        self._factory = factory

    async def execute(
        self,
        actor: Principal,
        project_id: UUID,
        member_key: str,
        role: ProjectRole,
        request_id: str = "",
    ) -> None:
        async with self._factory() as uow:
            actor_role = (
                None if actor.is_operator else await uow.memberships.role_for(project_id, actor.key)
            )
            allowed = actor.is_operator or role_allows(actor_role, ProjectAction.MANAGE_MEMBERS)
            if not allowed:
                await uow.access_audit.append(
                    AccessDecisionEvent.create(
                        actor.key, project_id, "membership.assign", "denied", request_id
                    )
                )
                await uow.commit()
                raise ProjectNotFound(f"project '{project_id}' not found")
            if await uow.projects.get(project_id) is None:
                raise ProjectNotFound(f"project '{project_id}' not found")
            await uow.memberships.upsert(ProjectMembership.create(project_id, member_key, role))
            await uow.access_audit.append(
                AccessDecisionEvent.create(
                    actor.key, project_id, "membership.assign", "allowed", request_id
                )
            )
            await uow.commit()


class ManageProjectMemberships:
    """Owner-only administration. This command never grants or mutates OWNER.

    Ownership transfer requires a separate explicit, audited workflow. No
    caller-controlled email/subject is treated as an authenticated identity:
    member_key must originate from the target user's verified identity API.
    """

    def __init__(self, factory: UnitOfWorkFactory) -> None:
        self._factory = factory

    async def _ensure_owner(
        self, uow: UnitOfWork, actor: Principal, project_id: UUID, request_id: str
    ) -> None:
        role = None if actor.is_operator else await uow.memberships.role_for(project_id, actor.key)
        if not (actor.is_operator or role is ProjectRole.OWNER):
            await uow.access_audit.append(
                AccessDecisionEvent.create(
                    actor.key, project_id, "membership.manage", "denied", request_id
                )
            )
            await uow.commit()
            # Hide project existence from all unauthorized principals.
            raise ProjectNotFound(f"project '{project_id}' not found")
        if await uow.projects.get(project_id) is None:
            raise ProjectNotFound(f"project '{project_id}' not found")

    async def list_members(
        self, actor: Principal, project_id: UUID, request_id: str = ""
    ) -> list[ProjectMembership]:
        async with self._factory() as uow:
            await self._ensure_owner(uow, actor, project_id, request_id)
            return await uow.memberships.list_for_project(project_id)

    async def assign(
        self,
        actor: Principal,
        project_id: UUID,
        member_key: str,
        role: ProjectRole,
        request_id: str = "",
    ) -> ProjectMembership:
        async with self._factory() as uow:
            await self._ensure_owner(uow, actor, project_id, request_id)
            existing = await uow.memberships.role_for(project_id, member_key)
            if role is ProjectRole.OWNER or existing is ProjectRole.OWNER or member_key == actor.key:
                raise InvalidMembershipChange(
                    "Owner memberships cannot be changed through this endpoint"
                )
            membership = ProjectMembership.create(project_id, member_key, role)
            await uow.memberships.upsert(membership)
            await uow.access_audit.append(
                AccessDecisionEvent.create(
                    actor.key, project_id, "membership.assign", "allowed", request_id
                )
            )
            await uow.commit()
            return membership

    async def revoke(
        self, actor: Principal, project_id: UUID, member_key: str, request_id: str = ""
    ) -> None:
        async with self._factory() as uow:
            await self._ensure_owner(uow, actor, project_id, request_id)
            existing = await uow.memberships.role_for(project_id, member_key)
            if existing is ProjectRole.OWNER or member_key == actor.key:
                raise InvalidMembershipChange(
                    "Owner memberships cannot be revoked through this endpoint"
                )
            if existing is None:
                raise ProjectNotFound("membership not found")
            if not await uow.memberships.delete(project_id, member_key):
                raise ProjectNotFound("membership not found")
            await uow.access_audit.append(
                AccessDecisionEvent.create(
                    actor.key, project_id, "membership.revoke", "allowed", request_id
                )
            )
            await uow.commit()
