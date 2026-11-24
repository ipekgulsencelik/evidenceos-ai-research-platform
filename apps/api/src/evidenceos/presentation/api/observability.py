"""Privacy-minimized API completion telemetry with a bounded event schema.

No raw URLs, query strings, request/response bodies, headers, credentials,
cookies, user identities, project identifiers, IPs, or exception messages.
Only predefined route families are emitted, never an incoming route value.
"""

import json
import logging
import sys
from collections.abc import Mapping

logger = logging.getLogger("evidenceos.http")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.propagate = False

_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_ROUTE_GROUPS = (
    ("/api/v1/health", "health"),
    ("/api/v1/projects", "projects"),
    ("/api/v1/academic", "academic"),
    ("/api/v1/documents", "documents"),
    ("/api/v1/evidence", "evidence"),
    ("/api/v1/literature", "literature"),
)


def route_group(scope: Mapping[str, object]) -> str:
    """Classify matched routes with fixed groups; never emit raw URL content."""
    # Classify using the path only after the framework matched a registered
    # route. Incoming path strings are never included in the emitted event.
    if scope.get("route") is None:
        return "unmatched"
    path = scope.get("path")
    if not isinstance(path, str):
        return "other"
    for prefix, family in _ROUTE_GROUPS:
        if path == prefix or path.startswith(prefix + "/"):
            return family
    return "other"


def observe_completion(
    *,
    request_id: str,
    method: str,
    status_code: int,
    elapsed_ms: int,
    group: str,
) -> None:
    """Emit a fixed-field JSON event, excluding successful health probe noise."""
    if group == "health" and status_code < 400:
        return
    # Group must only originate from the fixed route classifier.
    if group not in {*dict(_ROUTE_GROUPS).values(), "unmatched", "other"}:
        group = "other"
    event = {
        "event": "http.request.completed",
        "request_id": request_id,
        "method": method if method in _METHODS else "OTHER",
        "route_group": group,
        "status_code": status_code,
        "duration_ms": max(0, elapsed_ms),
    }
    logger.info("%s", json.dumps(event, separators=(",", ":"), ensure_ascii=True))
