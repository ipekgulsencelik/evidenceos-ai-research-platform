"""Source-backed academic research endpoints. No claim verification yet."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from evidenceos.application.use_cases.academic import SearchAcademicWorks, VerifyCitation
from evidenceos.domain.ports.academic import AcademicSearchProvider, CitationMetadataProvider
from evidenceos.presentation.api.academic_dependencies import (
    get_citation_provider,
    get_search_provider,
)
from evidenceos.presentation.api.academic_schemas import (
    AcademicWorkResponse,
    CitationCheckResponse,
    VerifyCitationRequest,
)

router = APIRouter(prefix="/academic", tags=["academic"])


@router.get("/works", response_model=list[AcademicWorkResponse])
async def search_works(
    query: Annotated[str, Query(min_length=3, max_length=200)],
    provider: Annotated[AcademicSearchProvider, Depends(get_search_provider)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[AcademicWorkResponse]:
    results = await SearchAcademicWorks(provider).execute(query, limit)
    return [AcademicWorkResponse.from_entity(work) for work in results]


@router.post("/citations/verify", response_model=CitationCheckResponse)
async def verify_citation(
    payload: VerifyCitationRequest,
    provider: Annotated[CitationMetadataProvider, Depends(get_citation_provider)],
) -> CitationCheckResponse:
    verification = await VerifyCitation(provider).execute(payload.doi, payload.expected_title)
    return CitationCheckResponse.from_entity(verification)
