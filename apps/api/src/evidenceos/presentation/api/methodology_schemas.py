"""HTTP response contract for source-anchored, provisional methodology review."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from evidenceos.domain.entities.literature import LiteratureFacet
from evidenceos.domain.entities.methodology import (
    MethodologyAspect,
    MethodologyReport,
    MethodologyStatus,
)


class MethodologyReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_to_share_quotes: bool = False


class MethodologySourceResponse(BaseModel):
    reference_id: str
    facet: LiteratureFacet
    locator: str
    quote: str


class MethodologyObservationResponse(BaseModel):
    aspect: MethodologyAspect
    status: MethodologyStatus
    observation: str
    review_question: str
    sources: list[MethodologySourceResponse]


class MethodologyReportResponse(BaseModel):
    project_id: UUID
    entry_id: UUID
    document_title: str
    model: str
    observations: list[MethodologyObservationResponse]
    discarded_model_observations: int
    caveat: str

    @classmethod
    def from_entity(cls, report: MethodologyReport) -> "MethodologyReportResponse":
        return cls(
            project_id=report.project_id,
            entry_id=report.entry_id,
            document_title=report.document_title,
            model=report.model,
            observations=[
                MethodologyObservationResponse(
                    aspect=item.aspect,
                    status=item.status,
                    observation=item.observation,
                    review_question=item.review_question,
                    sources=[
                        MethodologySourceResponse(
                            reference_id=source.reference_id,
                            facet=source.facet,
                            locator=source.locator,
                            quote=source.quote,
                        )
                        for source in item.sources
                    ],
                )
                for item in report.observations
            ],
            discarded_model_observations=report.discarded_model_observations,
            caveat=report.caveat,
        )
