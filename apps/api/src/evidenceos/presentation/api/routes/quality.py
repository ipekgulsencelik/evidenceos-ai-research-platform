"""Evidence coverage is automatic; reporting and bias concerns are human judgments."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from evidenceos.application.use_cases.quality import (
    GetQualityChecklist,
    ListQualityReviewHistory,
    SaveQualityReview,
    SaveQualityReviewCommand,
)
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.quality_schemas import (
    QualityChecklistResponse,
    QualityReviewRequest,
    QualityReviewResponse,
)

router = APIRouter(
    prefix="/projects/{project_id}/literature/{entry_id}",
    tags=["research quality and bias triage"],
)


@router.get("/quality-checklist", response_model=QualityChecklistResponse)
async def quality_checklist(
    project_id: UUID,
    entry_id: UUID,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> QualityChecklistResponse:
    result = await GetQualityChecklist(factory).execute(project_id, entry_id)
    return QualityChecklistResponse.from_entity(result)


@router.post(
    "/quality-reviews",
    status_code=status.HTTP_201_CREATED,
    response_model=QualityReviewResponse,
)
async def save_quality_review(
    project_id: UUID,
    entry_id: UUID,
    payload: QualityReviewRequest,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> QualityReviewResponse:
    result = await SaveQualityReview(factory).execute(
        SaveQualityReviewCommand(
            project_id=project_id,
            entry_id=entry_id,
            dimension=payload.dimension,
            reporting=payload.reporting,
            concern=payload.concern,
            checked_original=payload.checked_original,
            note=payload.note,
        )
    )
    return QualityReviewResponse.from_entity(result)


@router.get("/quality-reviews", response_model=list[QualityReviewResponse])
async def quality_review_history(
    project_id: UUID,
    entry_id: UUID,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[QualityReviewResponse]:
    result = await ListQualityReviewHistory(factory).execute(
        project_id, entry_id, limit=limit
    )
    return [QualityReviewResponse.from_entity(item) for item in result]
