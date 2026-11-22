"""Fail-closed interpretation of saved, source-grounded literature quotations."""

from uuid import UUID

from evidenceos.application.use_cases.selection import load_distinct_studies
from evidenceos.domain.entities.literature import FindingStatus, LiteratureFacet
from evidenceos.domain.entities.semantic import (
    SemanticComparison,
    SemanticDimension,
    SemanticExcerpt,
    SemanticGapReport,
)
from evidenceos.domain.errors import InvalidResearchWorkspace
from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.domain.ports.semantic import SemanticGapAnalyst

_FACET_DIMENSIONS = {
    LiteratureFacet.SAMPLE: SemanticDimension.POPULATION,
    LiteratureFacet.METHOD: SemanticDimension.STUDY_DESIGN,
    LiteratureFacet.INSTRUMENTS: SemanticDimension.MEASUREMENT,
    LiteratureFacet.FINDINGS: SemanticDimension.FINDINGS,
}
_CAVEAT = (
    "Preliminary AI comparisons based ONLY on exact quotations retained from selected "
    "PDF excerpts. A quotation match does not establish the truth of the interpretation. "
    "Different populations, measures and outcomes may not be comparable. This is NOT "
    "proof of a new research gap, scientific contradiction or causal relationship. "
    "Review original publications and the wider literature before making claims."
)


class CompareSemanticEvidence:
    def __init__(self, uow_factory: UnitOfWorkFactory, analyst: SemanticGapAnalyst) -> None:
        self._uow_factory = uow_factory
        self._analyst = analyst

    async def execute(
        self,
        project_id: UUID,
        entry_ids: tuple[UUID, ...],
        *,
        consent_to_share_quotes: bool,
    ) -> SemanticGapReport:
        if consent_to_share_quotes is not True:
            raise InvalidResearchWorkspace(
                "Explicit consent to send selected quoted excerpts to Groq is required"
            )
        entries = await load_distinct_studies(self._uow_factory, project_id, entry_ids)
        evidence: list[SemanticExcerpt] = []
        for index, entry in enumerate(entries, start=1):
            for finding in entry.profile.findings:
                dimension = _FACET_DIMENSIONS.get(finding.facet)
                if (
                    dimension is None
                    or finding.status is not FindingStatus.GROUNDED
                    or not finding.quote
                    or not finding.locator
                ):
                    continue
                evidence.append(
                    SemanticExcerpt(
                        reference_id=f"s{index}:{finding.facet.value}",
                        entry_id=entry.id,
                        document_title=entry.profile.document_title,
                        dimension=dimension,
                        locator=finding.locator,
                        quote=finding.quote,
                    )
                )

        sufficient = {
            dimension
            for dimension in SemanticDimension
            if len({x.entry_id for x in evidence if x.dimension is dimension}) >= 2
        }
        insufficient = tuple(d for d in SemanticDimension if d not in sufficient)
        available = tuple(x for x in evidence if x.dimension in sufficient)
        if not available:
            return SemanticGapReport(
                project_id, entry_ids, self._analyst.model_id, (), 0, insufficient, _CAVEAT
            )

        proposals = await self._analyst.compare(available)
        source_index = {item.reference_id: item for item in available}
        accepted: list[SemanticComparison] = []
        rejected = 0
        seen: set[SemanticDimension] = set()
        for proposal in proposals:
            ids = proposal.reference_ids
            refs = [source_index.get(ref_id) for ref_id in ids]
            correct = [
                ref for ref in refs if ref is not None and ref.dimension is proposal.dimension
            ]
            if (
                proposal.dimension not in sufficient
                or proposal.dimension in seen
                or not 2 <= len(ids) <= 10
                or len(set(ids)) != len(ids)
                or len(correct) != len(ids)
                or len({ref.entry_id for ref in correct}) < 2
                or not 5 <= len(proposal.summary.strip()) <= 500
                or not 5 <= len(proposal.research_question.strip()) <= 240
            ):
                rejected += 1
                continue
            accepted.append(
                SemanticComparison(
                    proposal.dimension,
                    proposal.kind,
                    proposal.summary.strip(),
                    proposal.research_question.strip(),
                    tuple(correct),
                )
            )
            seen.add(proposal.dimension)
        return SemanticGapReport(
            project_id,
            entry_ids,
            self._analyst.model_id,
            tuple(accepted),
            rejected,
            insufficient,
            _CAVEAT,
        )
