"""Evidence review: never present an invented model quotation as source evidence."""

from collections.abc import Sequence

from evidenceos.domain.entities.evidence import (
    EvidenceJudgment,
    EvidenceReport,
    EvidenceRow,
    EvidenceSource,
    EvidenceVerdict,
)
from evidenceos.domain.ports.evidence import EvidenceJudge


class InvalidEvidenceInput(ValueError):
    """Evidence inputs or attributions violate business constraints."""


class AssessEvidence:
    def __init__(self, judge: EvidenceJudge) -> None:
        self._judge = judge

    async def execute(self, claim: str, sources: Sequence[EvidenceSource]) -> EvidenceReport:
        if not 10 <= len(claim.strip()) <= 500 or not 1 <= len(sources) <= 3:
            raise InvalidEvidenceInput("Supply one claim (10-500 chars) and 1-3 passages")
        if len({source.source_id for source in sources}) != len(sources):
            raise InvalidEvidenceInput("Source identifiers must be unique")
        rows: list[EvidenceRow] = []
        for source in sources:
            judgment = await self._judge.judge(claim.strip(), source)
            reviewed = self._verify_quote(judgment, source)
            rows.append(
                EvidenceRow(
                    source_id=source.source_id,
                    title=source.title,
                    locator=source.locator,
                    verdict=reviewed.verdict,
                    quote=reviewed.quote,
                    explanation=reviewed.explanation,
                )
            )
        return EvidenceReport(claim=claim.strip(), model=self._judge.model_id, rows=tuple(rows))

    @staticmethod
    def _verify_quote(judgment: EvidenceJudgment, source: EvidenceSource) -> EvidenceJudgment:
        """Cited quotation must be a verbatim substring of the user-supplied text."""
        quote = judgment.quote
        if quote is not None and quote not in source.passage:
            return EvidenceJudgment(
                EvidenceVerdict.INSUFFICIENT,
                None,
                "Model quotation was not found verbatim in the supplied passage; review required.",
            )
        if judgment.verdict is not EvidenceVerdict.INSUFFICIENT and not quote:
            return EvidenceJudgment(
                EvidenceVerdict.INSUFFICIENT,
                None,
                "No exact supporting passage was provided by the model; review required.",
            )
        return judgment
