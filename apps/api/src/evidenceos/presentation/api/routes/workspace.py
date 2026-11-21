"""Save server-verified literature analysis; read projects and append review revisions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from evidenceos.application.use_cases.workspace import (
    GetLiteratureAnalysis,
    ListLiteratureAnalyses,
    ListReviewRevisions,
    SaveLiteratureAnalysis,
    SaveReviewCommand,
    SaveReviewRevision,
)
from evidenceos.domain.ports.document import DocumentTextExtractor
from evidenceos.domain.ports.literature import LiteratureAnalyst
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.routes.literature import (
    extract_pdf_profile,
    get_literature_analyst,
    get_pdf_extractor,
)
from evidenceos.presentation.api.workspace_schemas import (
    ReviewRevisionRequest,
    ReviewRevisionResponse,
    SavedLiteratureResponse,
)

router = APIRouter(prefix="/projects/{project_id}/literature", tags=["research workspace"])


@router.post(
    "/analyze-pdf",
    status_code=status.HTTP_201_CREATED,
    response_model=SavedLiteratureResponse,
)
async def analyze_and_save_pdf(
    project_id: UUID,
    request: Request,
    file: Annotated[UploadFile, File()],
    share_excerpts_with_ai: Annotated[bool, Form()],
    extractor: Annotated[DocumentTextExtractor, Depends(get_pdf_extractor)],
    analyst: Annotated[LiteratureAnalyst, Depends(get_literature_analyst)],
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> SavedLiteratureResponse:
    # Validate the destination before calling an external provider.
    from evidenceos.application.use_cases.projects import GetProject
    from evidenceos.domain.entities.project import ResearchDomain
    from evidenceos.domain.errors import InvalidResearchWorkspace

    project = await GetProject(uow_factory).execute(project_id)
    if project.domain is not ResearchDomain.ACADEMIC:
        raise InvalidResearchWorkspace("Literature workspace requires an academic project")
    profile = await extract_pdf_profile(
        request, file, share_excerpts_with_ai, extractor, analyst
    )
    saved = await SaveLiteratureAnalysis(uow_factory).execute(project_id, profile)
    return SavedLiteratureResponse.from_entity(saved)


@router.get("", response_model=list[SavedLiteratureResponse])
async def list_saved_literature(
    project_id: UUID,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SavedLiteratureResponse]:
    items = await ListLiteratureAnalyses(uow_factory).execute(project_id, limit=limit)
    return [SavedLiteratureResponse.from_entity(entry) for entry in items]


@router.get("/{entry_id}", response_model=SavedLiteratureResponse)
async def get_saved_literature(
    project_id: UUID,
    entry_id: UUID,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> SavedLiteratureResponse:
    entry = await GetLiteratureAnalysis(uow_factory).execute(project_id, entry_id)
    return SavedLiteratureResponse.from_entity(entry)


@router.post(
    "/{entry_id}/reviews",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewRevisionResponse,
)
async def create_review_revision(
    project_id: UUID,
    entry_id: UUID,
    payload: ReviewRevisionRequest,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> ReviewRevisionResponse:
    revision = await SaveReviewRevision(uow_factory).execute(
        SaveReviewCommand(
            project_id=project_id,
            entry_id=entry_id,
            facet=payload.facet,
            corrected_value=payload.corrected_value,
            note=payload.note,
            reviewed=payload.reviewed,
        )
    )
    return ReviewRevisionResponse.from_entity(revision)


@router.get("/{entry_id}/reviews", response_model=list[ReviewRevisionResponse])
async def get_review_history(
    project_id: UUID,
    entry_id: UUID,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ReviewRevisionResponse]:
    revisions = await ListReviewRevisions(uow_factory).execute(
        project_id, entry_id, limit=limit
    )
    return [ReviewRevisionResponse.from_entity(revision) for revision in revisions]
