"""Project lifecycle HTTP endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from evidenceos.application.use_cases.projects import (
    CreateProject,
    CreateProjectCommand,
    GetProject,
)
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.schemas import CreateProjectRequest, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    payload: CreateProjectRequest,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> ProjectResponse:
    project = await CreateProject(uow_factory).execute(
        CreateProjectCommand(title=payload.title, domain=payload.domain)
    )
    return ProjectResponse.from_entity(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> ProjectResponse:
    project = await GetProject(uow_factory).execute(project_id)
    return ProjectResponse.from_entity(project)
