"""Source-bounded evidence review domain model, independent of providers."""

from dataclasses import dataclass
from enum import StrEnum


class EvidenceVerdict(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_id: str
    title: str
    passage: str
    locator: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceJudgment:
    verdict: EvidenceVerdict
    quote: str | None
    explanation: str


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    source_id: str
    title: str
    locator: str | None
    verdict: EvidenceVerdict
    quote: str | None
    explanation: str


@dataclass(frozen=True, slots=True)
class EvidenceReport:
    claim: str
    model: str
    rows: tuple[EvidenceRow, ...]
