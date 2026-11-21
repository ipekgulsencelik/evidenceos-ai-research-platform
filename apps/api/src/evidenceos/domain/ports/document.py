"""Document parsing adapter contract: application never imports PDF libraries."""

from typing import Protocol

from evidenceos.domain.entities.document import ExtractedDocument


class DocumentTextExtractor(Protocol):
    def extract(self, data: bytes, filename: str) -> ExtractedDocument: ...
