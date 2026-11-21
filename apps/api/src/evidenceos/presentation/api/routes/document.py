"""Transient PDF upload and keyword-based, page-grounded passage retrieval."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from evidenceos.application.use_cases.document import RetrievePdfPassages
from evidenceos.domain.ports.document import DocumentTextExtractor
from evidenceos.infrastructure.providers.pypdf_document import (
    MAX_PDF_BYTES,
    PdfTooLarge,
    PypdfTextExtractor,
)
from evidenceos.presentation.api.document_schemas import DocumentReviewResponse

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_extractor() -> DocumentTextExtractor:
    return PypdfTextExtractor()


@router.post("/retrieve-passages", response_model=DocumentReviewResponse)
async def retrieve_passages(
    request: Request,
    file: Annotated[UploadFile, File(description="Locally parsed PDF, up to 8 MiB")],
    claim: Annotated[str, Form(min_length=10, max_length=500)],
    extractor: Annotated[DocumentTextExtractor, Depends(get_document_extractor)],
) -> DocumentReviewResponse:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdecimal() and int(content_length) > MAX_PDF_BYTES + 16384:
        raise PdfTooLarge("Upload exceeds the 8 MiB PDF limit")
    try:
        raw = await file.read(MAX_PDF_BYTES + 1)
    finally:
        await file.close()
    # PDF parsing must not block FastAPI's event loop.
    result = await asyncio.to_thread(
        RetrievePdfPassages(extractor).execute,
        raw,
        file.filename or "",
        claim,
    )
    return DocumentReviewResponse.from_entity(result)
