"""Evidence-coverage comparison over saved analyses; no external AI calls."""

from uuid import UUID

from evidenceos.domain.entities.gaps import (
    CoverageCandidate,
    GapComparison,
    GroundedReference,
)
from evidenceos.domain.entities.literature import FACET_ORDER, FindingStatus
from evidenceos.domain.errors import InvalidResearchWorkspace, LiteratureEntryNotFound
from evidenceos.domain.ports.repositories import UnitOfWorkFactory


class CompareEvidenceCoverage:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, project_id: UUID, entry_ids: tuple[UUID, ...]
    ) -> GapComparison:
        if not 2 <= len(entry_ids) <= 10 or len(set(entry_ids)) != len(entry_ids):
            raise InvalidResearchWorkspace("Select 2–10 distinct saved analyses")
        from evidenceos.application.use_cases.workspace import _require_project

        await _require_project(self._uow_factory, project_id)
        async with self._uow_factory() as uow:
            entries = [await uow.literature.get(entry_id) for entry_id in entry_ids]
        if any(entry is None or entry.project_id != project_id for entry in entries):
            raise LiteratureEntryNotFound("A selected analysis is not in this project")
        validated = [entry for entry in entries if entry is not None]
        if len({entry.profile.sha256 for entry in validated}) != len(validated):
            raise InvalidResearchWorkspace(
                "Select analyses of different PDFs, not repeated snapshots of one PDF"
            )
        candidates: list[CoverageCandidate] = []
        for facet in FACET_ORDER:
            references: list[GroundedReference] = []
            not_identified: list[UUID] = []
            rejected: list[UUID] = []
            for entry in validated:
                result = next(
                    (finding for finding in entry.profile.findings if finding.facet is facet),
                    None,
                )
                if (
                    result is not None
                    and result.status is FindingStatus.GROUNDED
                    and result.locator
                    and result.quote
                    and result.value
                ):
                    references.append(
                        GroundedReference(
                            entry.id,
                            entry.profile.document_title,
                            result.locator,
                            result.quote,
                            result.value,
                        )
                    )
                elif result is not None and result.status is FindingStatus.REJECTED_QUOTE:
                    rejected.append(entry.id)
                else:
                    not_identified.append(entry.id)
            if len(references) == len(validated):
                continue  # No extraction-coverage difference in this field.
            if references:
                recommendation = (
                    "Review the selected papers' original pages and extract the "
                    "missing or rejected field manually before proposing a research gap."
                )
            else:
                recommendation = (
                    "No verified quotation for this field was retrieved from these "
                    "excerpts. Search full papers manually before drawing conclusions."
                )
            candidates.append(
                CoverageCandidate(
                    facet,
                    len(references),
                    len(validated),
                    tuple(not_identified),
                    tuple(rejected),
                    tuple(references),
                    recommendation,
                )
            )
        return GapComparison(
            project_id,
            entry_ids,
            tuple(candidates),
            (
                "Extraction coverage comparison only, NOT evidence of a literature-wide "
                "research gap. Only selected saved PDF analyses are considered. "
                "'Not identified' can be caused by snippet selection, PDF parsing or "
                "AI extraction failures. Quotation matching does not establish "
                "scientific validity. Verify against original papers and broaden "
                "the search before stating a genuine gap."
            ),
        )
