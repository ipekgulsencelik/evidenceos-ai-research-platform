"""Researcher-reviewed reporting and possible bias concerns; no automatic risk score."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from evidenceos.domain.entities.literature import LiteratureFacet


class QualityDimension(StrEnum):
    DESIGN = "design"
    SAMPLING = "sampling"
    MEASUREMENT = "measurement"
    PSYCHOMETRICS = "psychometrics"
    ANALYSIS = "analysis"
    PRECISION = "precision"
    LIMITATIONS = "limitations"


class ReportingJudgment(StrEnum):
    NOT_ASSESSED = "not_assessed"
    REPORTED_IN_FULL_TEXT = "reported_in_full_text"
    UNCLEAR_AFTER_REVIEW = "unclear_after_review"
    NOT_REPORTED_IN_FULL_TEXT = "not_reported_in_full_text"
    NOT_APPLICABLE = "not_applicable"


class ConcernJudgment(StrEnum):
    NOT_ASSESSED = "not_assessed"
    POTENTIAL_CONCERN = "potential_concern"
    NO_CONCERN_IDENTIFIED = "no_concern_identified"


@dataclass(frozen=True, slots=True)
class QualitySource:
    facet: LiteratureFacet
    locator: str
    quote: str


@dataclass(frozen=True, slots=True)
class QualityIndicator:
    dimension: QualityDimension
    prompt: str
    source_excerpts: tuple[QualitySource, ...]
    # Presence of an excerpt is not proof that the reporting item is present.
    coverage: str


@dataclass(frozen=True, slots=True)
class QualityReviewRevision:
    id: UUID
    entry_id: UUID
    dimension: QualityDimension
    reporting: ReportingJudgment
    concern: ConcernJudgment
    checked_original: bool
    note: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        entry_id: UUID,
        dimension: QualityDimension,
        reporting: ReportingJudgment,
        concern: ConcernJudgment,
        checked_original: bool,
        note: str,
    ) -> "QualityReviewRevision":
        return cls(
            uuid4(), entry_id, dimension, reporting, concern,
            checked_original, note, datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class QualityChecklist:
    project_id: UUID
    entry_id: UUID
    document_title: str
    indicators: tuple[QualityIndicator, ...]
    latest_reviews: tuple[QualityReviewRevision, ...]
    caveat: str
