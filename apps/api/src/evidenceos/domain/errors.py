class DomainError(Exception):
    """An expected domain-level error."""


class InvalidProjectTitle(DomainError):
    """Raised for project titles that do not meet business constraints."""


class ProjectNotFound(DomainError):
    """Raised when a project identifier cannot be resolved."""
