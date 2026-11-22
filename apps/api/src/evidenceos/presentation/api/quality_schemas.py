"""Source-only checklist and append-only human judgment API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evidenceos.domain.entities.literature import LiteratureFacet
from evidenceos.domain.entities.quality import (
    ConcernJudgment,
    QualityChecklist,
    QualityDimension,
    QualityReviewRevision,
    ReportingJudgment,
)


class QualitySourceResponse(BaseModel):
    facet: LiteratureFacet
    locator: str
    quote: str


class QualityIndicatorResponse(BaseModel):
    dimension: QualityDimension
    prompt: str
    coverage: str
    source_excerpts: list[QualitySourceResponse]


class QualityReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dimension: QualityDimension
    reporting: ReportingJudgment = ReportingJudgment.NOT_ASSESSED
    concern: ConcernJudgment = ConcernJudgment.NOT_ASSESSED
    checked_original: bool = False
    note: str = Field(default="", max_length=1000)


class QualityReviewResponse(BaseModel):
    id: UUID
    entry_id: UUID
    dimension: QualityDimension
    reporting: ReportingJudgment
    concern: ConcernJudgment
    checked_original: bool
    note: str
    created_at: datetime

    @classmethod
    def from_entity(cls, entity: QualityReviewRevision) -> "QualityReviewResponse":
        return cls(
            id=entity.id,
            entry_id=entity.entry_id,
            dimension=entity.dimension,
            reporting=entity.reporting,
            concern=entity.concern,
            checked_original=entity.checked_original,
            note=entity.note,
            created_at=entity.created_at,
        )


class QualityChecklistResponse(BaseModel):
    project_id: UUID
    entry_id: UUID
    document_title: str
    indicators: list[QualityIndicatorResponse]
    latest_reviews: list[QualityReviewResponse]
    caveat: str

    @classmethod
    def from_entity(cls, entity: QualityChecklist) -> "QualityChecklistResponse":
        return cls(
            project_id=entity.project_id,
            entry_id=entity.entry_id,
            document_title=entity.document_title,
            indicators=[
                QualityIndicatorResponse(
                    dimension=row.dimension,
                    prompt=row.prompt,
                    coverage=row.coverage,
                    source_excerpts=[
                        QualitySourceResponse(
                            facet=source.facet,
                            locator=source.locator,
                            quote=source.quote,
                        )
                        for source in row.source_excerpts
                    ],
                )
                for row in entity.indicators
            ],
            latest_reviews=[
                QualityReviewResponse.from_entity(item) for item in entity.latest_reviews
            ],
            caveat=entity.caveat,
        )
