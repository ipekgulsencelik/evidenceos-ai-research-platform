"""Port for a substitutable methodology-review model provider."""

from typing import Protocol

from evidenceos.domain.entities.methodology import (
    MethodologySource,
    ProposedMethodologyObservation,
)


class MethodologyAnalyst(Protocol):
    @property
    def model_id(self) -> str: ...

    async def assess(
        self, sources: tuple[MethodologySource, ...]
    ) -> tuple[ProposedMethodologyObservation, ...]: ...
