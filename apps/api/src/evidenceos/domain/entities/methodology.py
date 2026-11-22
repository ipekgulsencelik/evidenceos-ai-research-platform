"""Source-anchored, provisional methodology-review data types."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from evidenceos.domain.entities.literature import LiteratureFacet


class MethodologyAspect(StrEnum):
    DESIGN = "study_design"
    SAMPLING = "sampling"
    INSTRUMENTS = "instruments"
    PSYCHOMETRICS = "psychometrics"
    STATISTICAL_METHODS = "statistical_methods"
    EFFECT_REPORTING = "effect_reporting"
    LIMITATIONS = "limitations"


class MethodologyStatus(StrEnum):
    REPORTED_IN_EXCERPT = "reported_in_excerpt"
    NEEDS_REVIEW = "needs_review"
    NOT_ASSESSABLE = "not_assessable"


@dataclass(frozen=True, slots=True)
class MethodologySource:
    reference_id: str
    facet: LiteratureFacet
    locator: str
    quote: str


@dataclass(frozen=True, slots=True)
class ProposedMethodologyObservation:
    aspect: MethodologyAspect
    status: MethodologyStatus
    observation: str
    review_question: str
    reference_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MethodologyObservation:
    aspect: MethodologyAspect
    status: MethodologyStatus
    observation: str
    review_question: str
    sources: tuple[MethodologySource, ...]


@dataclass(frozen=True, slots=True)
class MethodologyReport:
    project_id: UUID
    entry_id: UUID
    document_title: str
    model: str
    observations: tuple[MethodologyObservation, ...]
    discarded_model_observations: int
    caveat: str
