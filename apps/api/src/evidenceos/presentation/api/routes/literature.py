"""Explicitly consented research-content extraction from a local PDF."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from evidenceos.application.use_cases.literature import ExtractLiteratureProfile
from evidenceos.domain.ports.document import DocumentTextExtractor
from evidenceos.domain.ports.literature import LiteratureAnalyst
from evidenceos.infrastructure.providers.groq_literature import GroqLiteratureAnalyst
from evidenceos.infrastructure.providers.pypdf_document import (
    MAX_PDF_BYTES,
    PdfTooLarge,
    PypdfTextExtractor,
)
from evidenceos.presentation.api.literature_schemas import LiteratureProfileResponse

router = APIRouter(prefix="/literature", tags=["literature"])


def get_literature_analyst(request: Request) -> LiteratureAnalyst:
    return GroqLiteratureAnalyst(
        request.app.state.http_client,
        request.app.state.settings.groq_api_key,
        request.app.state.settings.groq_model,
    )


def get_pdf_extractor() -> DocumentTextExtractor:
    return PypdfTextExtractor()


@router.post("/analyze-pdf", response_model=LiteratureProfileResponse)
async def analyze_pdf(
    request: Request,
    file: Annotated[UploadFile, File()],
    share_excerpts_with_ai: Annotated[bool, Form()],
    extractor: Annotated[DocumentTextExtractor, Depends(get_pdf_extractor)],
    analyst: Annotated[LiteratureAnalyst, Depends(get_literature_analyst)],
) -> LiteratureProfileResponse:
    if not share_excerpts_with_ai:
        raise HTTPException(
            status_code=422,
            detail="Explicit consent is required before selected PDF excerpts go to Groq",
        )
    length = request.headers.get("content-length")
    if length and length.isdecimal() and int(length) > MAX_PDF_BYTES + 16384:
        raise PdfTooLarge("PDF upload exceeds the 8 MiB limit")
    try:
        data = await file.read(MAX_PDF_BYTES + 1)
    finally:
        await file.close()
    document = await asyncio.to_thread(extractor.extract, data, file.filename or "")
    profile = await ExtractLiteratureProfile(analyst).execute(document)
    return LiteratureProfileResponse.from_entity(profile)
