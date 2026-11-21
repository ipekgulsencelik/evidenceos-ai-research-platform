"""Application orchestration with provider abstractions."""

import re
from difflib import SequenceMatcher

from evidenceos.domain.entities.academic import (
    AcademicWork,
    CitationCheck,
    CitationStatus,
    normalize_doi,
    normalize_search,
)
from evidenceos.domain.ports.academic import AcademicSearchProvider, CitationMetadataProvider


class SearchAcademicWorks:
    def __init__(self, provider: AcademicSearchProvider) -> None:
        self._provider = provider

    async def execute(self, query: str, limit: int = 10) -> tuple[AcademicWork, ...]:
        return await self._provider.search(normalize_search(query, limit), limit)


class VerifyCitation:
    def __init__(self, provider: CitationMetadataProvider) -> None:
        self._provider = provider

    async def execute(self, doi: str, expected_title: str | None = None) -> CitationCheck:
        normalized_doi = normalize_doi(doi)
        metadata = await self._provider.lookup(normalized_doi)
        if metadata is None:
            return CitationCheck(normalized_doi, CitationStatus.NOT_FOUND_IN_CROSSREF, None)
        status = CitationStatus.VERIFIED
        if expected_title is not None:
            expected = self._normalize_title(expected_title)
            actual = self._normalize_title(metadata.title)
            if not expected or SequenceMatcher(None, expected, actual).ratio() < 0.90:
                status = CitationStatus.TITLE_MISMATCH
        return CitationCheck(normalized_doi, status, metadata)

    @staticmethod
    def _normalize_title(value: str) -> str:
        return " ".join(re.findall(r"\w+", value.casefold()))
