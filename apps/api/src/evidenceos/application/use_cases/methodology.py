"""Project-scoped methodological triage using only stored, source-matched excerpts."""

from uuid import UUID

from evidenceos.application.use_cases.workspace import GetLiteratureAnalysis
from evidenceos.domain.entities.literature import FindingStatus, LiteratureFacet
from evidenceos.domain.entities.methodology import (
    MethodologyAspect,
    MethodologyObservation,
    MethodologyReport,
    MethodologySource,
    MethodologyStatus,
)
from evidenceos.domain.errors import InvalidResearchWorkspace
from evidenceos.domain.ports.methodology import MethodologyAnalyst
from evidenceos.domain.ports.repositories import UnitOfWorkFactory

_ALLOWED: dict[MethodologyAspect, frozenset[LiteratureFacet]] = {
    MethodologyAspect.DESIGN: frozenset({LiteratureFacet.METHOD}),
    MethodologyAspect.SAMPLING: frozenset({LiteratureFacet.SAMPLE, LiteratureFacet.METHOD}),
    MethodologyAspect.INSTRUMENTS: frozenset({LiteratureFacet.INSTRUMENTS}),
    MethodologyAspect.PSYCHOMETRICS: frozenset({LiteratureFacet.INSTRUMENTS}),
    MethodologyAspect.STATISTICAL_METHODS: frozenset(
        {LiteratureFacet.METHOD, LiteratureFacet.FINDINGS}
    ),
    MethodologyAspect.EFFECT_REPORTING: frozenset({LiteratureFacet.FINDINGS}),
    MethodologyAspect.LIMITATIONS: frozenset({LiteratureFacet.LIMITATIONS}),
}
_QUESTIONS: dict[MethodologyAspect, str] = {
    MethodologyAspect.DESIGN: "What design and timing are reported in the full Methods?",
    MethodologyAspect.SAMPLING: "How were participants recruited and eligibility determined?",
    MethodologyAspect.INSTRUMENTS: "What constructs and tools were actually measured?",
    MethodologyAspect.PSYCHOMETRICS: "Are scale reliability and validity data documented?",
    MethodologyAspect.STATISTICAL_METHODS: "Which analyses and assumptions were reported?",
    MethodologyAspect.EFFECT_REPORTING: "Which effect sizes, uncertainty and p-values are given?",
    MethodologyAspect.LIMITATIONS: "Which limitations do the authors explicitly discuss?",
}
_CAVEAT = (
    "This is preliminary AI-assisted methodological TRIAGE of selected saved quotations, "
    "not a risk-of-bias assessment, quality score, verification of statistics or complete "
    "study appraisal. 'Not assessable' means the retained excerpt does not establish the "
    "information; it does NOT mean the full article omits it. Valid quotation identifiers "
    "do not guarantee the model's interpretation is accurate. Review the original full text."
)


class ReviewStudyMethodology:
    def __init__(self, factory: UnitOfWorkFactory, analyst: MethodologyAnalyst) -> None:
        self._factory = factory
        self._analyst = analyst

    async def execute(
        self, project_id: UUID, entry_id: UUID, *, consent_to_share_quotes: bool
    ) -> MethodologyReport:
        if consent_to_share_quotes is not True:
            raise InvalidResearchWorkspace(
                "Explicit consent to share saved source quotations with Groq is required"
            )
        entry = await GetLiteratureAnalysis(self._factory).execute(project_id, entry_id)
        sources = tuple(
            MethodologySource(
                reference_id="f:" + finding.facet.value,
                facet=finding.facet,
                locator=finding.locator,
                quote=finding.quote,
            )
            for finding in entry.profile.findings
            if finding.facet in {facet for allowed in _ALLOWED.values() for facet in allowed}
            and finding.status is FindingStatus.GROUNDED
            and finding.quote
            and finding.locator
        )
        index = {source.reference_id: source for source in sources}
        proposed = await self._analyst.assess(sources) if sources else ()
        accepted: dict[MethodologyAspect, MethodologyObservation] = {}
        discarded = 0
        for item in proposed:
            linked = [index.get(key) for key in item.reference_ids]
            valid = (
                item.aspect not in accepted
                and item.status is not MethodologyStatus.NOT_ASSESSABLE
                and 1 <= len(item.reference_ids) <= 3
                and len(set(item.reference_ids)) == len(item.reference_ids)
                and len(linked) == len(item.reference_ids)
                and all(
                    source is not None and source.facet in _ALLOWED[item.aspect]
                    for source in linked
                )
                and 5 <= len(item.observation.strip()) <= 450
                and 5 <= len(item.review_question.strip()) <= 240
            )
            if not valid:
                discarded += 1
                continue
            accepted[item.aspect] = MethodologyObservation(
                aspect=item.aspect,
                status=item.status,
                observation=item.observation.strip(),
                review_question=item.review_question.strip(),
                sources=tuple(source for source in linked if source is not None),
            )

        observations = tuple(
            accepted.get(aspect)
            or MethodologyObservation(
                aspect=aspect,
                status=MethodologyStatus.NOT_ASSESSABLE,
                observation=(
                    "Insufficient attributable detail in the saved excerpts. "
                    "Do not infer that the full publication lacks this information."
                ),
                review_question=_QUESTIONS[aspect],
                sources=(),
            )
            for aspect in MethodologyAspect
        )
        return MethodologyReport(
            project_id,
            entry_id,
            entry.profile.document_title,
            self._analyst.model_id,
            observations,
            discarded,
            _CAVEAT,
        )
