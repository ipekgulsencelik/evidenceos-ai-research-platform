from datetime import UTC, datetime
from uuid import UUID

import pytest

from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.errors import InvalidProjectTitle


def test_project_factory_normalizes_and_injects_identity() -> None:
    project_id = UUID("7f68b4b8-cd65-441a-b028-3810d001ab13")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    project = ResearchProject.create(
        "  My research  ", ResearchDomain.ACADEMIC, project_id=project_id, now=now
    )
    assert project.title == "My research"
    assert project.id == project_id
    assert project.created_at == now


@pytest.mark.parametrize("title", ["", "   ", "ab", "x" * 161])
def test_project_rejects_invalid_titles(title: str) -> None:
    with pytest.raises(InvalidProjectTitle):
        ResearchProject.create(title, ResearchDomain.LEGAL)
