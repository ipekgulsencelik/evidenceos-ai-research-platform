"""Model-independent evaluation contract (Dependency Inversion Principle)."""

from typing import Protocol

from evidenceos.domain.entities.evidence import EvidenceJudgment, EvidenceSource


class EvidenceJudge(Protocol):
    @property
    def model_id(self) -> str: ...

    async def judge(self, claim: str, source: EvidenceSource) -> EvidenceJudgment: ...
