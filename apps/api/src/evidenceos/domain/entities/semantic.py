"""Source-referenced, cautious semantic comparison types."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class SemanticDimension(StrEnum):
    POPULATION = "population"
    STUDY_DESIGN = "study_design"
    MEASUREMENT = "measurement"
    FINDINGS = "findings"


class ComparisonKind(StrEnum):
    POSSIBLE_DIFFERENCE = "possible_difference"
    POSSIBLE_ALIGNMENT = "possible_alignment"
    INSUFFICIENT_CONTEXT = "insufficient_context"


@dataclass(frozen=True, slots=True)
class SemanticExcerpt:
    reference_id: str
    entry_id: UUID
    document_title: str
    dimension: SemanticDimension
    locator: str
    quote: str


@dataclass(frozen=True, slots=True)
class ProposedSemanticComparison:
    dimension: SemanticDimension
    kind: ComparisonKind
    summary: str
    research_question: str
    reference_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticComparison:
    dimension: SemanticDimension
    kind: ComparisonKind
    summary: str
    research_question: str
    references: tuple[SemanticExcerpt, ...]


@dataclass(frozen=True, slots=True)
class SemanticGapReport:
    project_id: UUID
    document_ids: tuple[UUID, ...]
    model: str
    candidates: tuple[SemanticComparison, ...]
    skipped_candidates: int
    insufficient_dimensions: tuple[SemanticDimension, ...]
    caveat: str
