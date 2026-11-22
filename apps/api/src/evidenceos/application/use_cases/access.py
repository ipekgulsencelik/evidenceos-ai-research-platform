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
from evidenceos.domain.errors import ProjectNotFound
from evidenceos.domain.ports.repositories import UnitOfWorkFactory


class EnforceProjectAccess:
    def __init__(self, factory: UnitOfWorkFactory) -> None:
        self._factory = factory

    async def execute(
        self, actor: Principal, project_id: UUID, action: ProjectAction, request_id: str = ""
    ) -> None:
        async with self._factory() as uow:
            role = None if actor.is_operator else await uow.memberships.role_for(
                project_id, actor.key
            )
            allowed = actor.is_operator or role_allows(role, action)
            # Only writes and denials are journalled to keep read traffic bounded.
            if action is not ProjectAction.READ or not allowed:
                await uow.access_audit.append(
                    AccessDecisionEvent.create(
                        actor.key, project_id, action.value,
                        "allowed" if allowed else "denied", request_id,
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
        self, actor: Principal, project_id: UUID,
        member_key: str, role: ProjectRole, request_id: str = "",
    ) -> None:
        async with self._factory() as uow:
            actor_role = None if actor.is_operator else await uow.memberships.role_for(
                project_id, actor.key
            )
            allowed = actor.is_operator or role_allows(
                actor_role, ProjectAction.MANAGE_MEMBERS
            )
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
