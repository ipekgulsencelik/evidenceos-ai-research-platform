"""Trust boundary for local operator, server-to-server and OIDC resource modes."""

import hashlib
import hmac
import logging

from fastapi import HTTPException, Request, status

from evidenceos.domain.entities.access import LOCAL_OPERATOR, SERVICE_OPERATOR, Principal
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.oidc import (
    InvalidOidcToken,
    OidcAccessTokenVerifier,
    OidcProviderUnavailable,
)

logger = logging.getLogger(__name__)


def _reject(request: Request) -> None:
    # Never record tokens, request content, unverified claims or header values.
    logger.warning(
        "security.auth_denied request_id=%s",
        getattr(request.state, "request_id", "unknown"),
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
    )


async def validate_service_credential(request: Request) -> Principal:
    """Issue a principal only after the configured credential check succeeds."""
    settings: Settings = request.app.state.settings
    if settings.security_mode == "local":
        return LOCAL_OPERATOR

    supplied = request.headers.getlist("authorization")
    if len(supplied) != 1:
        _reject(request)
    scheme, separator, token = supplied[0].partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not token
        or token != token.strip()
        or any(character.isspace() for character in token)
    ):
        _reject(request)

    if settings.security_mode == "oidc":
        verifier: OidcAccessTokenVerifier = request.app.state.oidc_verifier
        try:
            return await verifier.verify(token)
        except InvalidOidcToken:
            _reject(request)
        except OidcProviderUnavailable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Identity verification temporarily unavailable",
                headers={"Cache-Control": "no-store", "Retry-After": "5"},
            ) from None

    if settings.api_service_token is not None:
        expected = hashlib.sha256(settings.api_service_token.encode("utf-8")).digest()
        actual = hashlib.sha256(token.encode("utf-8")).digest()
        if hmac.compare_digest(expected, actual):
            return SERVICE_OPERATOR
    _reject(request)
