"""OpenAlex metadata search; explicit upstream failures are not empty searches."""

from contextlib import suppress
from typing import Any

import httpx

from evidenceos.domain.entities.academic import AcademicWork, normalize_doi
from evidenceos.domain.errors import AcademicConfigurationError, AcademicProviderError, InvalidDoi


class OpenAlexSearchAdapter:
    URL = "https://api.openalex.org/works"

    def __init__(self, client: httpx.AsyncClient, api_key: str | None) -> None:
        self._client = client
        self._api_key = api_key

    async def search(self, query: str, limit: int) -> tuple[AcademicWork, ...]:
        if not self._api_key:
            raise AcademicConfigurationError("OpenAlex API key is not configured")
        try:
            response = await self._client.get(
                self.URL,
                params={"search": query, "per_page": limit, "api_key": self._api_key},
            )
            response.raise_for_status()
            payload: Any = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise ValueError("Unexpected OpenAlex payload")
            return tuple(
                work
                for entry in payload["results"]
                if isinstance(entry, dict) and (work := self._parse_work(entry)) is not None
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise AcademicProviderError("OpenAlex search temporarily unavailable") from exc

    @staticmethod
    def _parse_work(item: dict[str, Any]) -> AcademicWork | None:
        source_id, title = item.get("id"), item.get("display_name") or item.get("title")
        if not isinstance(source_id, str) or not isinstance(title, str) or not title.strip():
            return None
        raw_doi = item.get("doi")
        doi = None
        if isinstance(raw_doi, str):
            with suppress(InvalidDoi):
                doi = normalize_doi(raw_doi)
        authorships = item.get("authorships") or []
        if not isinstance(authorships, list):
            authorships = []
        authors = tuple(
            author["author"]["display_name"]
            for author in authorships
            if isinstance(author, dict)
            and isinstance(author.get("author"), dict)
            and isinstance(author["author"].get("display_name"), str)
        )
        year = item.get("publication_year")
        return AcademicWork(
            source_id=source_id,
            title=title.strip(),
            doi=doi,
            publication_year=year if isinstance(year, int) and not isinstance(year, bool) else None,
            authors=authors,
            source_url=source_id,
        )
