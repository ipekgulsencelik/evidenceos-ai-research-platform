"""Public API contracts, intentionally separate from domain entities."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evidenceos.domain.entities.project import ResearchDomain, ResearchProject


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=3, max_length=160)
    domain: ResearchDomain


class ProjectResponse(BaseModel):
    id: UUID
    title: str
    domain: ResearchDomain
    created_at: datetime

    @classmethod
    def from_entity(cls, project: ResearchProject) -> "ProjectResponse":
        return cls(
            id=project.id,
            title=project.title,
            domain=project.domain,
            created_at=project.created_at,
        )


class StatusResponse(BaseModel):
    status: str
