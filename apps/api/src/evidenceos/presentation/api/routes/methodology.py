"""Consent-gated on-demand methodological review of one saved academic paper."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from evidenceos.application.use_cases.methodology import ReviewStudyMethodology
from evidenceos.domain.ports.methodology import MethodologyAnalyst
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.infrastructure.providers.groq_methodology import GroqMethodologyAnalyst
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.methodology_schemas import (
    MethodologyReportResponse,
    MethodologyReviewRequest,
)

router = APIRouter(
    prefix="/projects/{project_id}/literature/{entry_id}", tags=["methodology review"]
)


def get_methodology_analyst(request: Request) -> MethodologyAnalyst:
    return GroqMethodologyAnalyst(
        request.app.state.http_client,
        request.app.state.settings.groq_api_key,
        request.app.state.settings.groq_model,
    )


@router.post("/methodology-review", response_model=MethodologyReportResponse)
async def review_methodology(
    project_id: UUID,
    entry_id: UUID,
    payload: MethodologyReviewRequest,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    analyst: Annotated[MethodologyAnalyst, Depends(get_methodology_analyst)],
) -> MethodologyReportResponse:
    result = await ReviewStudyMethodology(factory, analyst).execute(
        project_id, entry_id, consent_to_share_quotes=payload.consent_to_share_quotes
    )
    return MethodologyReportResponse.from_entity(result)
