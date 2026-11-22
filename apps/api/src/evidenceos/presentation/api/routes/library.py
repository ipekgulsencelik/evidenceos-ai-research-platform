"""Local-only project catalog and deterministic, source-linked coverage comparison."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from evidenceos.application.use_cases.gaps import CompareEvidenceCoverage
from evidenceos.application.use_cases.library import (
    ListLibraryItems,
    UpdateCatalogCommand,
    UpdateLibraryMetadata,
)
from evidenceos.domain.entities.library import ReadingStatus
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.library_schemas import (
    CompareGapsRequest,
    GapComparisonResponse,
    LibraryItemResponse,
    LibraryMetadataRequest,
    LibraryMetadataResponse,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["research library"])


@router.get("/library", response_model=list[LibraryItemResponse])
async def list_library(
    project_id: UUID,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    query: Annotated[str, Query(max_length=120)] = "",
    status: ReadingStatus | None = None,
    tag: Annotated[str, Query(max_length=32)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[LibraryItemResponse]:
    items = await ListLibraryItems(uow_factory).execute(
        project_id, query=query.strip(), status=status, tag=tag.strip(), limit=limit
    )
    return [LibraryItemResponse.from_entity(item) for item in items]


@router.put("/library/{entry_id}", response_model=LibraryMetadataResponse)
async def update_library_metadata(
    project_id: UUID,
    entry_id: UUID,
    payload: LibraryMetadataRequest,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> LibraryMetadataResponse:
    metadata = await UpdateLibraryMetadata(uow_factory).execute(
        UpdateCatalogCommand(
            project_id=project_id,
            entry_id=entry_id,
            status=payload.status,
            tags=tuple(payload.tags),
        )
    )
    return LibraryMetadataResponse.from_entity(metadata)


@router.post("/research-gaps", response_model=GapComparisonResponse)
async def compare_research_coverage(
    project_id: UUID,
    payload: CompareGapsRequest,
    uow_factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
) -> GapComparisonResponse:
    report = await CompareEvidenceCoverage(uow_factory).execute(
        project_id, tuple(payload.entry_ids)
    )
    return GapComparisonResponse.from_entity(report)
