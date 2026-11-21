"""Bounded, local-only text extraction from user-supplied PDFs (no OCR)."""

import hashlib
import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from evidenceos.domain.entities.document import DocumentPage, ExtractedDocument

MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_PAGE_CHARS = 30000
MAX_TOTAL_CHARS = 160000


class InvalidPdfDocument(ValueError):
    """Uploaded bytes cannot safely be processed as a searchable PDF."""


class PdfTooLarge(InvalidPdfDocument):
    """Reject uploads that exceed strict size or extraction limits."""


def clean_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if len(name) > 180 or len(name) < 5 or not name.lower().endswith(".pdf"):
        raise InvalidPdfDocument("Provide a PDF filename no longer than 180 characters")
    # Do not leak control characters or use client-provided directory paths.
    if any(ord(char) < 32 for char in name):
        raise InvalidPdfDocument("Invalid filename")
    return name


class PypdfTextExtractor:
    def extract(self, data: bytes, filename: str) -> ExtractedDocument:
        name = clean_filename(filename)
        if len(data) > MAX_PDF_BYTES:
            raise PdfTooLarge("PDF exceeds the 8 MiB upload limit")
        if len(data) < 8 or not data.startswith(b"%PDF-"):
            raise InvalidPdfDocument("File is not a valid PDF")
        try:
            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise InvalidPdfDocument("Password-protected PDFs are not supported")
            page_count = len(reader.pages)
            if page_count < 1:
                raise InvalidPdfDocument("PDF has no pages")
            if page_count > MAX_PDF_PAGES:
                raise PdfTooLarge("PDF exceeds the 30-page limit")
            pages: list[DocumentPage] = []
            total_chars = 0
            for number, page in enumerate(reader.pages, start=1):
                raw = page.extract_text() or ""
                if len(raw) > MAX_PAGE_CHARS:
                    raise PdfTooLarge("A PDF page exceeds the text extraction limit")
                text = re.sub(r"\s+", " ", raw).strip()
                total_chars += len(text)
                if total_chars > MAX_TOTAL_CHARS:
                    raise PdfTooLarge("Extracted PDF text exceeds the safety limit")
                if text:
                    pages.append(DocumentPage(number, text))
        except (PdfReadError, ValueError, TypeError, KeyError, OSError) as exc:
            if isinstance(exc, InvalidPdfDocument):
                raise
            raise InvalidPdfDocument("PDF is damaged or cannot be parsed") from exc

        if not pages:
            raise InvalidPdfDocument(
                "No selectable text found. Scanned PDFs need OCR, which is not supported yet"
            )
        return ExtractedDocument(
            title=name,
            sha256=hashlib.sha256(data).hexdigest(),
            page_count=page_count,
            pages=tuple(pages),
        )
