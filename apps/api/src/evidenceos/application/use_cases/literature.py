"""Six-field scientific literature profile with exact, page-grounded quotations."""

from evidenceos.domain.entities.document import ExtractedDocument
from evidenceos.domain.entities.literature import (
    FACET_ORDER,
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
    LiteratureRejectionReason,
    LiteratureSnippet,
    ProposedFinding,
)
from evidenceos.domain.ports.literature import LiteratureAnalyst

# Lexical selection is only a recall heuristic; never a relevance probability.
_FACET_TERMS: dict[LiteratureFacet, tuple[str, ...]] = {
    LiteratureFacet.AIM: (
        "aim",
        "objective",
        "purpose",
        "hypothesis",
        "goal",
        "amaç",
        "hedef",
    ),
    LiteratureFacet.METHOD: (
        "method",
        "design",
        "cross-sectional",
        "cohort",
        "randomized",
        "trial",
        "qualitative",
        "yöntem",
        "tasarım",
        "kesitsel",
    ),
    LiteratureFacet.SAMPLE: (
        "participant",
        "sample",
        "recruit",
        "adolescent",
        "student",
        "respondent",
        "örneklem",
        "katılımcı",
        "ergen",
    ),
    LiteratureFacet.INSTRUMENTS: (
        "scale",
        "questionnaire",
        "survey",
        "instrument",
        "measure",
        "inventory",
        "ölçek",
        "anket",
        "ölçeği",
        "envanter",
    ),
    LiteratureFacet.FINDINGS: (
        "result",
        "finding",
        "association",
        "significant",
        "effect",
        "observed",
        "bulgu",
        "sonuç",
        "ilişki",
        "etki",
    ),
    LiteratureFacet.LIMITATIONS: (
        "limitation",
        "limitation of",
        "bias",
        "caution",
        "constraint",
        "sınırlılık",
        "kısıtlılık",
        "yanlılık",
        "sınırlı",
    ),
}


def _windows(text: str, width: int = 1150, overlap: int = 140) -> list[str]:
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + width)
        if end < len(text):
            boundary = text.rfind(" ", start + width // 2, end)
            if boundary > start:
                end = boundary
        excerpt = text[start:end].strip()
        if excerpt:
            windows.append(excerpt)
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return windows


def collect_snippets(document: ExtractedDocument) -> tuple[LiteratureSnippet, ...]:
    """Select up to 12 literal PDF substrings with stable original PDF page references."""
    windows: list[tuple[int, int, str]] = []
    for document_page in document.pages:
        for i, text in enumerate(_windows(document_page.text), start=1):
            if len(text) >= 30:
                windows.append((document_page.number, i, text))

    chosen: dict[str, LiteratureSnippet] = {}
    for facet in FACET_ORDER:
        ranked: list[tuple[int, int, int, str]] = []
        for page_number, index, text in windows:
            folded = text.casefold()
            matches = sum(term in folded for term in _FACET_TERMS[facet])
            if matches:
                ranked.append((-matches, page_number, index, text))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        for _, page_number, index, passage in ranked[:2]:
            snippet_id = f"p{page_number}-w{index}"
            chosen[snippet_id] = LiteratureSnippet(
                snippet_id=snippet_id,
                locator=f"PDF page {page_number}",
                passage=passage,
            )
    return tuple(chosen[key] for key in sorted(chosen))


def _review_proposal(
    facet: LiteratureFacet,
    candidates: list[ProposedFinding],
    available: dict[str, LiteratureSnippet],
) -> LiteratureFinding:
    """Fail closed; never preserve an unsupported value or made-up quotation."""
    if not candidates or (
        len(candidates) == 1
        and candidates[0].value is None
        and candidates[0].quote is None
        and candidates[0].snippet_id is None
    ):
        return LiteratureFinding(facet, FindingStatus.NOT_IDENTIFIED, None, None, None)
    if len(candidates) != 1:
        return LiteratureFinding(
            facet,
            FindingStatus.REJECTED_QUOTE,
            None,
            None,
            None,
            LiteratureRejectionReason.DUPLICATE_FIELD,
        )

    proposal = candidates[0]
    if proposal.value is None or proposal.quote is None:
        return LiteratureFinding(
            facet,
            FindingStatus.REJECTED_QUOTE,
            None,
            None,
            None,
            LiteratureRejectionReason.INCOMPLETE_EVIDENCE,
        )
    value = proposal.value.strip()
    quote = proposal.quote.strip()
    if not 1 <= len(value) <= 500 or not 5 <= len(quote) <= 600:
        return LiteratureFinding(
            facet,
            FindingStatus.REJECTED_QUOTE,
            None,
            None,
            None,
            LiteratureRejectionReason.INVALID_LENGTH,
        )

    specified = available.get(proposal.snippet_id or "")
    if specified is not None and quote in specified.passage:
        return LiteratureFinding(
            facet, FindingStatus.GROUNDED, value, quote, specified.locator
        )

    # The model may reference the wrong snippet ID. Only recover an exact quote
    # when all matched source snippets point to the SAME PDF page. Never guess.
    matching = {source.locator for source in available.values() if quote in source.passage}
    if not matching:
        reason = LiteratureRejectionReason.QUOTE_NOT_FOUND
    elif len(matching) > 1:
        reason = LiteratureRejectionReason.AMBIGUOUS_LOCATION
    else:
        return LiteratureFinding(
            facet,
            FindingStatus.GROUNDED,
            value,
            quote,
            next(iter(matching)),
            locator_repaired=True,
        )
    return LiteratureFinding(facet, FindingStatus.REJECTED_QUOTE, None, None, None, reason)


class ExtractLiteratureProfile:
    def __init__(self, analyst: LiteratureAnalyst) -> None:
        self._analyst = analyst

    async def execute(self, document: ExtractedDocument) -> LiteratureProfile:
        snippets = collect_snippets(document)
        proposals = await self._analyst.extract(snippets) if snippets else ()
        available = {snippet.snippet_id: snippet for snippet in snippets}
        grouped: dict[LiteratureFacet, list[ProposedFinding]] = {}
        for proposal in proposals:
            grouped.setdefault(proposal.facet, []).append(proposal)

        findings = [
            _review_proposal(facet, grouped.get(facet, []), available)
            for facet in FACET_ORDER
        ]

        return LiteratureProfile(
            document_title=document.title,
            sha256=document.sha256,
            page_count=document.page_count,
            text_page_count=len(document.pages),
            model=self._analyst.model_id,
            findings=tuple(findings),
            caveat=(
                "Preliminary AI interpretation of selected PDF excerpts only. "
                "Quotations are checked against selected PDF excerpts; recovered locators " 
                "are marked. The interpretation, "
                "research methodology and original PDF must be verified by a human. "
                "Not identified means not found in the selected excerpts, not absent "
                "from the paper. This is not systematic review data extraction."
            ),
        )
