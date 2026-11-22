"""No semantic model call without explicit consent and project-scoped selection."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from evidenceos.application.use_cases.semantic import CompareSemanticEvidence
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.domain.ports.semantic import SemanticGapAnalyst
from evidenceos.infrastructure.providers.groq_semantic import GroqSemanticGapAnalyst
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.semantic_schemas import (
    SemanticComparisonRequest,
    SemanticGapReportResponse,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["semantic literature comparison"])


def get_semantic_analyst(request: Request) -> SemanticGapAnalyst:
    return GroqSemanticGapAnalyst(
        request.app.state.http_client,
        request.app.state.settings.groq_api_key,
        request.app.state.settings.groq_model,
    )


@router.post("/semantic-gaps", response_model=SemanticGapReportResponse)
async def compare_semantic_gaps(
    project_id: UUID,
    payload: SemanticComparisonRequest,
    factory: Annotated[UnitOfWorkFactory, Depends(get_uow_factory)],
    analyst: Annotated[SemanticGapAnalyst, Depends(get_semantic_analyst)],
) -> SemanticGapReportResponse:
    result = await CompareSemanticEvidence(factory, analyst).execute(
        project_id,
        tuple(payload.entry_ids),
        consent_to_share_quotes=payload.consent_to_share_quotes,
    )
    return SemanticGapReportResponse.from_entity(result)
