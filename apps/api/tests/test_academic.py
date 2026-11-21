"""No live calls: prove use-case semantics, provider behavior and API wiring."""

from collections.abc import Iterator
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from evidenceos.application.use_cases.academic import SearchAcademicWorks, VerifyCitation
from evidenceos.domain.entities.academic import (
    AcademicWork,
    CitationMetadata,
    CitationStatus,
    normalize_doi,
)
from evidenceos.domain.errors import AcademicConfigurationError, AcademicProviderError, InvalidDoi
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.providers.crossref import CrossrefCitationAdapter
from evidenceos.infrastructure.providers.openalex import OpenAlexSearchAdapter
from evidenceos.presentation.api.academic_dependencies import (
    get_citation_provider,
    get_search_provider,
)
from evidenceos.presentation.api.app import create_app


class FakeAcademicSearch:
    def __init__(self) -> None:
        self.seen: tuple[str, int] | None = None

    async def search(self, query: str, limit: int) -> tuple[AcademicWork, ...]:
        self.seen = (query, limit)
        return (AcademicWork("https://openalex.org/W1", "Study", None, 2025, (), "https://openalex.org/W1"),)


class FakeCitationLookup:
    def __init__(self, title: str | None) -> None:
        self.title = title

    async def lookup(self, doi: str) -> CitationMetadata | None:
        if self.title is None:
            return None
        return CitationMetadata(doi, self.title, 2024, f"https://doi.org/{doi}")


@pytest.mark.asyncio
async def test_search_use_case_normalizes_query() -> None:
    provider = FakeAcademicSearch()
    results = await SearchAcademicWorks(provider).execute("  artificial  intelligence ", 5)
    assert provider.seen == ("artificial intelligence", 5)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_citation_verification_distinguishes_not_found_title_and_valid() -> None:
    yes = await VerifyCitation(FakeCitationLookup("AI research: a review")).execute(
        "https://doi.org/10.1234/ABC", "ai research a review"
    )
    assert yes.status is CitationStatus.VERIFIED
    assert yes.doi == "10.1234/abc"
    no = await VerifyCitation(FakeCitationLookup("A different study")).execute(
        "10.1234/abc", "My target title"
    )
    assert no.status is CitationStatus.TITLE_MISMATCH
    missing = await VerifyCitation(FakeCitationLookup(None)).execute("10.1234/abc")
    assert missing.status is CitationStatus.NOT_FOUND_IN_CROSSREF


@pytest.mark.parametrize("value", ["", "not-a-doi", "10.123/foo", "https://example.com/10.1234/abc", "10.1234/hello world"])
def test_rejects_bad_doi(value: str) -> None:
    with pytest.raises(InvalidDoi):
        normalize_doi(value)


@pytest.mark.asyncio
async def test_openalex_normalizes_metadata_and_includes_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == "test-key"
        assert request.url.params["search"] == "AI eating"
        return httpx.Response(200, json={"results": [{"id": "https://openalex.org/W1", "title": "A study", "doi": "https://doi.org/10.1000/XYZ", "publication_year": 2024, "authorships": [{"author": {"display_name": "J. Doe"}}]}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAlexSearchAdapter(client, "test-key")
        works = await adapter.search("AI eating", 3)
    assert works[0].doi == "10.1000/xyz"
    assert works[0].authors == ("J. Doe",)


@pytest.mark.asyncio
async def test_openalex_without_key_is_configuration_error() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        with pytest.raises(AcademicConfigurationError):
            await OpenAlexSearchAdapter(client, None).search("query", 5)


@pytest.mark.asyncio
async def test_openalex_upstream_failure_is_not_empty_result() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(429))) as client:
        with pytest.raises(AcademicProviderError):
            await OpenAlexSearchAdapter(client, "test-key").search("query", 5)


@pytest.mark.asyncio
async def test_crossref_lookup_not_found_and_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["mailto"] == "research@example.org"
        assert request.url.path.endswith("10.1000%2Fxyz") or request.url.path.endswith("10.1000/xyz")
        return httpx.Response(200, json={"message": {"title": ["Example paper"], "published": {"date-parts": [[2023, 3]]}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await CrossrefCitationAdapter(client, "research@example.org").lookup("10.1000/xyz")
    assert metadata is not None and metadata.publication_year == 2023
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404))) as client:
        assert await CrossrefCitationAdapter(client).lookup("10.1000/xyz") is None


@pytest.mark.asyncio
async def test_crossref_rejects_invalid_upstream_payload() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))) as client:
        with pytest.raises(AcademicProviderError):
            await CrossrefCitationAdapter(client).lookup("10.1000/xyz")


@pytest.fixture
def academic_client() -> Iterator[TestClient]:
    app = create_app(Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test"))
    app.dependency_overrides[get_search_provider] = FakeAcademicSearch
    app.dependency_overrides[get_citation_provider] = lambda: FakeCitationLookup("A study")
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_search_api(academic_client: TestClient) -> None:
    response = academic_client.get("/api/v1/academic/works", params={"query": "AI research", "limit": 2})
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Study"
    assert UUID(response.headers["X-Request-ID"])


def test_invalid_search_api(academic_client: TestClient) -> None:
    assert academic_client.get("/api/v1/academic/works", params={"query": "x"}).status_code == 422
    assert academic_client.get("/api/v1/academic/works", params={"query": "some topic", "limit": 200}).status_code == 422


def test_citation_api(academic_client: TestClient) -> None:
    response = academic_client.post("/api/v1/academic/citations/verify", json={"doi": "10.1000/X", "expected_title": "A study"})
    assert response.status_code == 200
    assert response.json()["status"] == "verified"


def test_invalid_doi_api(academic_client: TestClient) -> None:
    response = academic_client.post("/api/v1/academic/citations/verify", json={"doi": "invalid-doi"})
    assert response.status_code == 422
