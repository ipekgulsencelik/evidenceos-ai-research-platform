"""Project permission dependency: identity is issued by trusted auth infrastructure."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from evidenceos.application.use_cases.access import EnforceProjectAccess
from evidenceos.domain.entities.access import Principal, ProjectAction
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.security import validate_service_credential


def required_project_action(request: Request) -> ProjectAction:
    if request.url.path.endswith("/access-audit"):
        return ProjectAction.MANAGE_MEMBERS
    if request.method in ("GET", "HEAD"):
        return ProjectAction.READ
    if request.url.path.endswith("/reviews") or request.url.path.endswith("/quality-reviews"):
        return ProjectAction.REVIEW
    if request.url.path.endswith("/memberships"):
        return ProjectAction.MANAGE_MEMBERS
    return ProjectAction.WRITE


async def require_project_access(
    request: Request,
    actor: Annotated[Principal, Depends(validate_service_credential)],
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> None:
    raw_project_id = request.path_params.get("project_id")
    if raw_project_id is None:
        # The project collection is handled separately: list is filtered per
        # principal; creation inserts an owner membership in the same transaction.
        return
    try:
        project_id = UUID(str(raw_project_id))
    except ValueError:
        # Let Pydantic return 422 for an invalid path UUID.
        return
    await EnforceProjectAccess(uow_factory).execute(
        actor,
        project_id,
        required_project_action(request),
        getattr(request.state, "request_id", ""),
    )
