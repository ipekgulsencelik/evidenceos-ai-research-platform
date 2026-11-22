"""The AI proposes comparisons; the application authenticates every source ID."""

from typing import Protocol

from evidenceos.domain.entities.semantic import (
    ProposedSemanticComparison,
    SemanticExcerpt,
)


class SemanticGapAnalyst(Protocol):
    @property
    def model_id(self) -> str: ...

    async def compare(
        self, evidence: tuple[SemanticExcerpt, ...]
    ) -> tuple[ProposedSemanticComparison, ...]: ...
