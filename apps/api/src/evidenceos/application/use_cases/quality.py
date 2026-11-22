"""Deterministic evidence pointers plus independently saved human judgments."""

from dataclasses import dataclass
from uuid import UUID

from evidenceos.application.use_cases.workspace import GetLiteratureAnalysis
from evidenceos.domain.entities.literature import FindingStatus, LiteratureFacet
from evidenceos.domain.entities.quality import (
    ConcernJudgment,
    QualityChecklist,
    QualityDimension,
    QualityIndicator,
    QualityReviewRevision,
    QualitySource,
    ReportingJudgment,
)
from evidenceos.domain.errors import InvalidResearchWorkspace
from evidenceos.domain.ports.repositories import UnitOfWorkFactory

# Generic reporting prompts, NOT a validated study-specific bias instrument.
_INDICATORS: dict[QualityDimension, tuple[str, tuple[LiteratureFacet, ...]]] = {
    QualityDimension.DESIGN: (
        "Are design, timing, and causal-inference limits sufficiently described?",
        (LiteratureFacet.METHOD,),
    ),
    QualityDimension.SAMPLING: (
        "Are recruitment, eligibility, selection and participant flow documented?",
        (LiteratureFacet.SAMPLE, LiteratureFacet.METHOD),
    ),
    QualityDimension.MEASUREMENT: (
        "Are measured constructs and instrument administration described?",
        (LiteratureFacet.INSTRUMENTS,),
    ),
    QualityDimension.PSYCHOMETRICS: (
        "Is validity and reliability evidence suitable for this sample reported?",
        (LiteratureFacet.INSTRUMENTS,),
    ),
    QualityDimension.ANALYSIS: (
        "Are statistical models, assumptions, missing data and confounding addressed?",
        (LiteratureFacet.METHOD, LiteratureFacet.FINDINGS),
    ),
    QualityDimension.PRECISION: (
        "Are effect estimates, precision and uncertainty reported and interpretable?",
        (LiteratureFacet.FINDINGS,),
    ),
    QualityDimension.LIMITATIONS: (
        "Are potential biases, generalizability and study limitations considered?",
        (LiteratureFacet.LIMITATIONS,),
    ),
}
_CAVEAT = (
    "This is a generic reporting checklist and researcher annotation workspace, "
    "NOT a validated risk-of-bias instrument, automated quality score, or proof "
    "of methodological rigor. A matched excerpt only indicates available text, "
    "not that the question is answered. Missing excerpts do NOT imply missing "
    "information in the full publication. Researcher judgments are self-reported "
    "and must be based on full-text inspection; select an appropriate validated "
    "study-design-specific tool for formal risk-of-bias assessment."
)


@dataclass(frozen=True, slots=True)
class SaveQualityReviewCommand:
    project_id: UUID
    entry_id: UUID
    dimension: QualityDimension
    reporting: ReportingJudgment
    concern: ConcernJudgment
    checked_original: bool
    note: str


class GetQualityChecklist:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, project_id: UUID, entry_id: UUID) -> QualityChecklist:
        entry = await GetLiteratureAnalysis(self._uow_factory).execute(project_id, entry_id)
        fields = {finding.facet: finding for finding in entry.profile.findings}
        indicators: list[QualityIndicator] = []
        for dimension, (prompt, facets) in _INDICATORS.items():
            sources: list[QualitySource] = []
            for facet in facets:
                finding = fields.get(facet)
                if (
                    finding is not None
                    and finding.status is FindingStatus.GROUNDED
                    and finding.quote
                    and finding.locator
                ):
                    sources.append(QualitySource(facet, finding.locator, finding.quote))
            indicators.append(
                QualityIndicator(
                    dimension,
                    prompt,
                    tuple(sources),
                    "excerpt_available" if sources else "not_assessable_from_excerpts",
                )
            )
        async with self._uow_factory() as uow:
            recent = [
                await uow.quality.latest(entry_id, dimension) for dimension in QualityDimension
            ]
        return QualityChecklist(
            project_id,
            entry_id,
            entry.profile.document_title,
            tuple(indicators),
            tuple(review for review in recent if review is not None),
            _CAVEAT,
        )


class SaveQualityReview:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: SaveQualityReviewCommand) -> QualityReviewRevision:
        if not command.checked_original and (
            command.reporting is not ReportingJudgment.NOT_ASSESSED
            or command.concern is not ConcernJudgment.NOT_ASSESSED
        ):
            raise InvalidResearchWorkspace(
                "Full-text researcher judgments require confirming original PDF review"
            )
        if len(command.note) > 1000:
            raise InvalidResearchWorkspace("Quality review note exceeds 1000 characters")
        await GetLiteratureAnalysis(self._uow_factory).execute(command.project_id, command.entry_id)
        revision = QualityReviewRevision.create(
            command.entry_id,
            command.dimension,
            command.reporting,
            command.concern,
            command.checked_original,
            command.note,
        )
        async with self._uow_factory() as uow:
            await uow.quality.add(revision)
            await uow.commit()
        return revision


class ListQualityReviewHistory:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, project_id: UUID, entry_id: UUID, *, limit: int = 100
    ) -> list[QualityReviewRevision]:
        await GetLiteratureAnalysis(self._uow_factory).execute(project_id, entry_id)
        async with self._uow_factory() as uow:
            return await uow.quality.history(entry_id, limit=limit)
