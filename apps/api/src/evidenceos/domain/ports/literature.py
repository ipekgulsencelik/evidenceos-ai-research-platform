"""Interface segregation: an analyst does not parse PDF files."""

from typing import Protocol

from evidenceos.domain.entities.literature import LiteratureSnippet, ProposedFinding


class LiteratureAnalyst(Protocol):
    @property
    def model_id(self) -> str: ...

    async def extract(
        self, snippets: tuple[LiteratureSnippet, ...]
    ) -> tuple[ProposedFinding, ...]: ...
