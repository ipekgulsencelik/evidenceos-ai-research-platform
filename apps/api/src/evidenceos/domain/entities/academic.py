"""Academic metadata. DOI existence is not evidence for a scientific claim."""

import re
from dataclasses import dataclass
from enum import StrEnum

from evidenceos.domain.errors import InvalidDoi, InvalidSearchQuery


@dataclass(frozen=True, slots=True)
class AcademicWork:
    source_id: str
    title: str
    doi: str | None
    publication_year: int | None
    authors: tuple[str, ...]
    source_url: str


@dataclass(frozen=True, slots=True)
class CitationMetadata:
    doi: str
    title: str
    publication_year: int | None
    source_url: str


class CitationStatus(StrEnum):
    VERIFIED = "verified"
    TITLE_MISMATCH = "title_mismatch"
    NOT_FOUND_IN_CROSSREF = "not_found_in_crossref"


@dataclass(frozen=True, slots=True)
class CitationCheck:
    doi: str
    status: CitationStatus
    metadata: CitationMetadata | None


def normalize_doi(raw: str) -> str:
    """Normalize a DOI identifier, never a user-provided upstream URL."""
    candidate = raw.strip()
    if candidate.lower().startswith("doi:"):
        candidate = candidate[4:].strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
        if candidate.lower().startswith(prefix):
            candidate = candidate[len(prefix) :]
            break
    if len(candidate) > 255 or not re.fullmatch(r"10\.\d{4,9}/\S+", candidate):
        raise InvalidDoi("invalid DOI identifier")
    if any(ord(char) < 33 or ord(char) > 126 for char in candidate):
        raise InvalidDoi("invalid DOI identifier")
    return candidate.lower()


def normalize_search(query: str, limit: int) -> str:
    normalized = " ".join(query.split())
    if not 3 <= len(normalized) <= 200 or not 1 <= limit <= 25:
        raise InvalidSearchQuery("query must have 3-200 characters and limit must be 1-25")
    return normalized
