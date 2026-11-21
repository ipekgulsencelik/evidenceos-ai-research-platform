"""PDF extraction and retrieval: local-only, deterministic and page grounded."""

import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from evidenceos.application.use_cases.document import InvalidDocumentClaim, RetrievePdfPassages
from evidenceos.domain.entities.document import DocumentPage, ExtractedDocument
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.providers.pypdf_document import (
    MAX_PDF_BYTES,
    InvalidPdfDocument,
    PdfTooLarge,
    PypdfTextExtractor,
)
from evidenceos.presentation.api.app import create_app


def sample_pdf(text: str | None = None, *, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if text is not None:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): ref})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("test-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class FakeExtractor:
    def extract(self, data: bytes, filename: str) -> ExtractedDocument:
        return ExtractedDocument(
            filename,
            "1234567890abcdef",
            2,
            (
                DocumentPage(
                    1,
                    "Adolescent AI chatbot use was associated with emotional support "
                    "among surveyed students, but causation was not established.",
                ),
                DocumentPage(
                    2,
                    "Researchers evaluated sleep patterns using a self-report questionnaire. "
                    "This paragraph is unrelated to chatbot use.",
                ),
            ),
        )


def test_retrieval_is_deterministic_and_page_grounded() -> None:
    use_case = RetrievePdfPassages(FakeExtractor())
    result = use_case.execute(b"unused", "sample.pdf", "AI chatbot emotional support adolescents")
    assert result.page_count == 2
    assert result.text_page_count == 2
    assert result.passages
    assert result.passages[0].locator == "PDF page 1"
    assert result.passages[0].lexical_score > 0
    assert "associated with emotional support" in result.passages[0].passage
    assert result.passages[0].source_id.startswith("pdf-1234567890ab-p1")
    assert "does not establish" in result.caveat


def test_unmatched_terms_do_not_fabricate_excerpts() -> None:
    result = RetrievePdfPassages(FakeExtractor()).execute(
        b"unused", "sample.pdf", "Neuroimaging brain scans and biomarkers"
    )
    assert result.passages == ()


@pytest.mark.parametrize("claim", ["abc", "a" * 501, "the and for that with from"])
def test_claim_requires_valid_terms(claim: str) -> None:
    with pytest.raises(InvalidDocumentClaim):
        RetrievePdfPassages(FakeExtractor()).execute(b"unused", "sample.pdf", claim)


def test_real_pdf_text_is_extracted_with_page_number_and_hash() -> None:
    raw = sample_pdf("Adolescent chatbot use was associated with emotional wellbeing in a study.")
    document = PypdfTextExtractor().extract(raw, "C:\\fake\\study.pdf")
    assert document.title == "study.pdf"
    assert document.page_count == 1
    assert document.pages[0].number == 1
    assert "Adolescent chatbot" in document.pages[0].text
    assert len(document.sha256) == 64
    result = RetrievePdfPassages(PypdfTextExtractor()).execute(
        raw, "study.pdf", "chatbot emotional wellbeing adolescents"
    )
    assert result.passages and result.passages[0].locator == "PDF page 1"


@pytest.mark.parametrize(
    ("data", "name"),
    [
        (b"not a pdf", "study.pdf"),
        (b"%PDF-" + b"invalid bytes", "study.pdf"),
        (b"%PDF-" + b"invalid bytes", "not-pdf.txt"),
    ],
)
def test_reject_invalid_pdf(data: bytes, name: str) -> None:
    with pytest.raises(InvalidPdfDocument):
        PypdfTextExtractor().extract(data, name)


def test_reject_pdf_without_selectable_text() -> None:
    with pytest.raises(InvalidPdfDocument, match="No selectable text"):
        PypdfTextExtractor().extract(sample_pdf(), "scan.pdf")


def test_reject_encrypted_pdf() -> None:
    with pytest.raises(InvalidPdfDocument, match="Password"):
        PypdfTextExtractor().extract(sample_pdf("Secret document", encrypted=True), "locked.pdf")


def test_bounded_upload_does_not_process_oversized_data() -> None:
    with pytest.raises(PdfTooLarge):
        PypdfTextExtractor().extract(b"%PDF-1.4" + b"x" * MAX_PDF_BYTES, "big.pdf")


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    with TestClient(app) as client:
        yield client


def test_pdf_upload_endpoint_returns_ranked_candidates(api_client: TestClient) -> None:
    result = api_client.post(
        "/api/v1/documents/retrieve-passages",
        files={
            "file": (
                "my-study.pdf",
                sample_pdf(
                    "Adolescent chatbot use was associated with emotional wellbeing in a study."
                ),
                "application/pdf",
            )
        },
        data={"claim": "Chatbot use affects adolescent emotional wellbeing"},
    )
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["title"] == "my-study.pdf"
    assert data["page_count"] == 1
    assert len(data["passages"]) == 1
    assert data["passages"][0]["locator"] == "PDF page 1"


def test_pdf_upload_endpoint_rejects_nonpdf(api_client: TestClient) -> None:
    result = api_client.post(
        "/api/v1/documents/retrieve-passages",
        files={"file": ("paper.pdf", b"hello world", "application/pdf")},
        data={"claim": "AI chatbot support among adolescent groups"},
    )
    assert result.status_code == 422


def test_pdf_upload_endpoint_validates_claim(api_client: TestClient) -> None:
    result = api_client.post(
        "/api/v1/documents/retrieve-passages",
        files={"file": ("paper.pdf", sample_pdf("The chatbot may be useful."), "application/pdf")},
        data={"claim": "short"},
    )
    assert result.status_code == 422
