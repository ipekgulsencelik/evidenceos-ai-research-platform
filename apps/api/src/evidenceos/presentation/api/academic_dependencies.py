"""Wiring of academic adapters at the outermost composition boundary."""

from fastapi import Request

from evidenceos.domain.ports.academic import AcademicSearchProvider, CitationMetadataProvider
from evidenceos.infrastructure.providers.crossref import CrossrefCitationAdapter
from evidenceos.infrastructure.providers.openalex import OpenAlexSearchAdapter


def get_search_provider(request: Request) -> AcademicSearchProvider:
    return OpenAlexSearchAdapter(
        request.app.state.http_client, request.app.state.settings.openalex_api_key
    )


def get_citation_provider(request: Request) -> CitationMetadataProvider:
    return CrossrefCitationAdapter(
        request.app.state.http_client, request.app.state.settings.crossref_contact_email
    )
