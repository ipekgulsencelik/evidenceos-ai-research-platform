"""Crossref DOI metadata lookup; never interprets absence as a nonexistent DOI globally."""

from typing import Any
from urllib.parse import quote

import httpx

from evidenceos.domain.entities.academic import CitationMetadata
from evidenceos.domain.errors import AcademicProviderError


class CrossrefCitationAdapter:
    BASE_URL = "https://api.crossref.org/works/"

    def __init__(self, client: httpx.AsyncClient, contact_email: str | None = None) -> None:
        self._client = client
        self._contact_email = contact_email

    async def lookup(self, doi: str) -> CitationMetadata | None:
        params = {"mailto": self._contact_email} if self._contact_email else None
        headers = {"User-Agent": "EvidenceOS/0.2 (+https://github.com/ipekgulsencelik/evidenceos-ai-research-platform)"}
        try:
            response = await self._client.get(
                self.BASE_URL + quote(doi, safe=""), params=params, headers=headers
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload: Any = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
                raise ValueError("Unexpected Crossref payload")
            item = payload["message"]
            titles = item.get("title")
            if not isinstance(titles, list) or not titles or not isinstance(titles[0], str):
                raise ValueError("Crossref title missing")
            year = None
            published = item.get("published") or item.get("issued")
            if isinstance(published, dict):
                parts = published.get("date-parts")
                if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                    value = parts[0][0]
                    if isinstance(value, int) and not isinstance(value, bool):
                        year = value
            return CitationMetadata(
                doi=doi,
                title=titles[0].strip(),
                publication_year=year,
                source_url=f"https://doi.org/{doi}",
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            raise AcademicProviderError("Crossref lookup temporarily unavailable") from exc
