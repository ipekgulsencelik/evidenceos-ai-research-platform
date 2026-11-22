"""Issuer-scoped identities and project authorization rules (framework independent)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid4


class ProjectRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class ProjectAction(StrEnum):
    READ = "read"
    WRITE = "write"
    REVIEW = "review"
    MANAGE_MEMBERS = "manage_members"


_ALLOWED: dict[ProjectRole, frozenset[ProjectAction]] = {
    ProjectRole.OWNER: frozenset(ProjectAction),
    ProjectRole.EDITOR: frozenset(
        (ProjectAction.READ, ProjectAction.WRITE, ProjectAction.REVIEW)
    ),
    ProjectRole.REVIEWER: frozenset((ProjectAction.READ, ProjectAction.REVIEW)),
    ProjectRole.VIEWER: frozenset((ProjectAction.READ,)),
}


@dataclass(frozen=True, slots=True)
class Principal:
    """Only trusted authentication infrastructure may construct user principals."""

    key: str
    kind: str  # 'local_operator', 'service_operator', or 'oidc_user'

    @property
    def is_operator(self) -> bool:
        return self.kind in ("local_operator", "service_operator")


def stable_subject_key(issuer: str, subject: str) -> str:
    """Namespaced pseudonymous subject key; never trust client-supplied identities."""
    if not issuer or not subject or len(issuer) > 2048 or len(subject) > 1024:
        raise ValueError("invalid external identity")
    return sha256(f"{len(issuer)}:{issuer}{subject}".encode()).hexdigest()


LOCAL_OPERATOR = Principal(stable_subject_key("evidenceos:local", "operator"), "local_operator")
SERVICE_OPERATOR = Principal(stable_subject_key("evidenceos:service", "operator"), "service_operator")


@dataclass(frozen=True, slots=True)
class ProjectMembership:
    project_id: UUID
    principal_key: str
    role: ProjectRole
    created_at: datetime

    @classmethod
    def create(
        cls, project_id: UUID, principal_key: str, role: ProjectRole
    ) -> "ProjectMembership":
        if len(principal_key) != 64 or any(c not in "0123456789abcdef" for c in principal_key):
            raise ValueError("invalid principal key")
        return cls(project_id, principal_key, role, datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class AccessDecisionEvent:
    id: UUID
    actor_key: str
    project_id: UUID | None
    action: str
    outcome: str  # allowed / denied: a permission decision, not operation success
    request_id: str
    created_at: datetime

    @classmethod
    def create(
        cls, actor_key: str, project_id: UUID | None, action: str, outcome: str,
        request_id: str = "",
    ) -> "AccessDecisionEvent":
        if outcome not in ("allowed", "denied"):
            raise ValueError("invalid access decision")
        if not action or len(action) > 80 or len(request_id) > 64:
            raise ValueError("invalid access event")
        return cls(uuid4(), actor_key, project_id, action, outcome, request_id, datetime.now(UTC))


def role_allows(role: ProjectRole | None, action: ProjectAction) -> bool:
    """Absent membership always denies; role permissions are explicit."""
    return role is not None and action in _ALLOWED[role]
