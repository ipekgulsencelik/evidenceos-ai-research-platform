"""Single-operator service credential enforcement at the HTTP boundary.

This is not user authentication or project-level authorization. It protects the
backend while a real identity provider and per-project permissions are built.
"""

import hashlib
import hmac
import logging

from fastapi import HTTPException, Request, status

from evidenceos.infrastructure.config import Settings

logger = logging.getLogger(__name__)


def validate_service_credential(request: Request) -> None:
    """Fail closed for service-token mode; leave local development unchanged."""
    settings: Settings = request.app.state.settings
    if settings.security_mode == "local":
        return

    supplied = request.headers.getlist("authorization")
    if len(supplied) == 1:
        scheme, separator, token = supplied[0].partition(" ")
        if (
            separator
            and scheme.lower() == "bearer"
            and token
            and token == token.strip()
            and not any(character.isspace() for character in token)
            and settings.api_service_token is not None
        ):
            expected = hashlib.sha256(settings.api_service_token.encode("utf-8")).digest()
            actual = hashlib.sha256(token.encode("utf-8")).digest()
            if hmac.compare_digest(expected, actual):
                return

    # Never record the credential, request body or untrusted authorization header.
    logger.warning(
        "security.auth_denied request_id=%s",
        getattr(request.state, "request_id", "unknown"),
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={
            "WWW-Authenticate": "Bearer",
            "Cache-Control": "no-store",
        },
    )
