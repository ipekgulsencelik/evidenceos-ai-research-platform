"""Immutable, provider-independent literature extraction types."""

from dataclasses import dataclass
from enum import StrEnum


class LiteratureFacet(StrEnum):
    AIM = "aim"
    METHOD = "method"
    SAMPLE = "sample"
    INSTRUMENTS = "instruments"
    FINDINGS = "findings"
    LIMITATIONS = "limitations"


FACET_ORDER = tuple(LiteratureFacet)


class FindingStatus(StrEnum):
    GROUNDED = "grounded"
    NOT_IDENTIFIED = "not_identified"
    REJECTED_QUOTE = "rejected_quote"


class LiteratureRejectionReason(StrEnum):
    DUPLICATE_FIELD = "duplicate_field"
    INCOMPLETE_EVIDENCE = "incomplete_evidence"
    QUOTE_NOT_FOUND = "quote_not_found"
    AMBIGUOUS_LOCATION = "ambiguous_location"
    INVALID_LENGTH = "invalid_length"


@dataclass(frozen=True, slots=True)
class LiteratureSnippet:
    snippet_id: str
    locator: str
    passage: str


@dataclass(frozen=True, slots=True)
class ProposedFinding:
    facet: LiteratureFacet
    snippet_id: str | None
    quote: str | None
    value: str | None


@dataclass(frozen=True, slots=True)
class LiteratureFinding:
    facet: LiteratureFacet
    status: FindingStatus
    value: str | None
    quote: str | None
    locator: str | None
    rejection_reason: LiteratureRejectionReason | None = None
    locator_repaired: bool = False


@dataclass(frozen=True, slots=True)
class LiteratureProfile:
    document_title: str
    sha256: str
    page_count: int
    text_page_count: int
    model: str
    findings: tuple[LiteratureFinding, ...]
    caveat: str
