"""Provider-neutral PDF extraction and retrieval results."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentPage:
    number: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    title: str
    sha256: str
    page_count: int
    pages: tuple[DocumentPage, ...]


@dataclass(frozen=True, slots=True)
class RelevantPassage:
    source_id: str
    title: str
    locator: str
    passage: str
    matched_terms: tuple[str, ...]
    lexical_score: float


@dataclass(frozen=True, slots=True)
class DocumentReview:
    title: str
    sha256: str
    page_count: int
    text_page_count: int
    passages: tuple[RelevantPassage, ...]
    caveat: str
