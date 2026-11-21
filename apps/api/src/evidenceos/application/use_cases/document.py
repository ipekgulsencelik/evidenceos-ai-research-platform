"""Deterministic, page-grounded candidate retrieval, not scientific verification."""

import re

from evidenceos.domain.entities.document import DocumentReview, RelevantPassage
from evidenceos.domain.ports.document import DocumentTextExtractor

_TERMS = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "that", "with", "from", "this", "have",
        "been", "were", "their", "into", "between", "about", "which",
        "study", "research", "are", "was", "not", "only", "our",
        "bir", "ile", "olan", "icin", "için", "veya", "gibi", "daha",
        "olarak", "ancak", "üzerine", "arasında", "hakkında", "sonuç",
        "çalışma", "çalışmada", "yapılan", "the", "birlikte",
    }
)


class InvalidDocumentClaim(ValueError):
    """Claim is not suitable for lexical passage retrieval."""


def _tokens(text: str) -> set[str]:
    return {term for term in _TERMS.findall(text.casefold()) if term not in _STOPWORDS}


def _windows(text: str, *, width: int = 850, overlap: int = 130) -> list[str]:
    """Overlapping exact substrings. Never generate or reword evidence passages."""
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + width)
        if end < len(text):
            boundary = text.rfind(" ", start + width // 2, end)
            if boundary > start:
                end = boundary
        sample = text[start:end].strip()
        if len(sample) >= 30:
            windows.append(sample)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return windows


class RetrievePdfPassages:
    def __init__(self, extractor: DocumentTextExtractor) -> None:
        self._extractor = extractor

    def execute(self, data: bytes, filename: str, claim: str) -> DocumentReview:
        normalized_claim = claim.strip()
        if not 10 <= len(normalized_claim) <= 500:
            raise InvalidDocumentClaim("Claim must contain between 10 and 500 characters")
        claim_terms = _tokens(normalized_claim)
        if not claim_terms:
            raise InvalidDocumentClaim("Claim needs searchable words")

        document = self._extractor.extract(data, filename)
        candidates: list[tuple[float, int, int, RelevantPassage]] = []
        for page in document.pages:
            for index, passage in enumerate(_windows(page.text), start=1):
                matching = tuple(sorted(claim_terms.intersection(_tokens(passage))))
                if not matching:
                    continue
                score = round(len(matching) / len(claim_terms), 3)
                candidates.append(
                    (
                        -score,
                        page.number,
                        index,
                        RelevantPassage(
                            source_id=f"pdf-{document.sha256[:12]}-p{page.number}-s{index}",
                            title=document.title,
                            locator=f"PDF page {page.number}",
                            passage=passage,
                            matched_terms=matching,
                            lexical_score=score,
                        ),
                    )
                )

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return DocumentReview(
            title=document.title,
            sha256=document.sha256,
            page_count=document.page_count,
            text_page_count=len(document.pages),
            passages=tuple(item[3] for item in candidates[:3]),
            caveat=(
                "Keyword overlap retrieves candidate text; it does not establish support, "
                "contradiction or scientific validity. Review the PDF and page numbers. "
                "Nothing is sent to an AI provider unless you separately choose Assess claim."
            ),
        )
