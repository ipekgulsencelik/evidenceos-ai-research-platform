class DomainError(Exception):
    """An expected domain-level error."""


class InvalidProjectTitle(DomainError):
    """Raised for project titles that do not meet business constraints."""


class ProjectNotFound(DomainError):
    """Raised when a project identifier cannot be resolved."""


class InvalidDoi(ValueError):
    """Supplied identifier does not match DOI format."""


class InvalidSearchQuery(ValueError):
    """Invalid academic search arguments."""


class AcademicProviderError(RuntimeError):
    """External academic metadata provider failed or returned bad data."""


class AcademicConfigurationError(RuntimeError):
    """Required academic provider configuration is missing."""


class LiteratureEntryNotFound(DomainError):
    """No literature analysis was found within the specified project."""


class InvalidResearchWorkspace(DomainError):
    """A research workspace operation is invalid or not permitted."""


class InvalidMembershipChange(DomainError):
    """A membership mutation violates owner protection or transfer policy."""
