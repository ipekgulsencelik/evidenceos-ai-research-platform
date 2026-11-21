"""Passage-based evidence assessment. Does not crawl paywalled article text."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from evidenceos.application.use_cases.evidence import AssessEvidence
from evidenceos.domain.ports.evidence import EvidenceJudge
from evidenceos.infrastructure.providers.groq_evidence import GroqEvidenceJudge
from evidenceos.presentation.api.evidence_schemas import (
    AssessEvidenceRequest,
    EvidenceReportResponse,
)

router = APIRouter(prefix="/evidence", tags=["evidence"])


def get_evidence_judge(request: Request) -> EvidenceJudge:
    return GroqEvidenceJudge(
        client=request.app.state.http_client,
        api_key=request.app.state.settings.groq_api_key,
        model=request.app.state.settings.groq_model,
    )


@router.post("/assess", response_model=EvidenceReportResponse)
async def assess_evidence(
    payload: AssessEvidenceRequest,
    judge: Annotated[EvidenceJudge, Depends(get_evidence_judge)],
) -> EvidenceReportResponse:
    report = await AssessEvidence(judge).execute(
        payload.claim, [source.to_entity() for source in payload.sources]
    )
    return EvidenceReportResponse.from_entity(report)
