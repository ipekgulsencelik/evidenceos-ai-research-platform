"""Trusted OIDC JWT access-token verification for an API resource server.

Never read key locations from tokens. A configured HTTPS JWKS endpoint is the
single trust anchor; token-supplied jku, x5u, jwk, or alg cannot replace it.
"""

import asyncio
import json
import time
from typing import Any

import httpx
import jwt
from jwt.exceptions import InvalidTokenError, PyJWKError

from evidenceos.domain.entities.access import Principal, stable_subject_key
from evidenceos.infrastructure.config import Settings


class InvalidOidcToken(Exception):
    """Caller cannot be authenticated."""


class OidcProviderUnavailable(Exception):
    """Configured identity provider's signing keys are unavailable."""


class OidcAccessTokenVerifier:
    """Asynchronous JWKS fetch, bounded caching and RS256-only validation."""

    def __init__(self, config: Settings, client: httpx.AsyncClient) -> None:
        if config.security_mode != "oidc":
            raise ValueError("OIDC verifier requires OIDC security mode")
        self._issuer = config.oidc_issuer or ""
        self._audience = config.oidc_audience or ""
        self._jwks_url = config.oidc_jwks_url or ""
        self._client = client
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._next_unknown_kid_refresh = 0.0
        self._retry_after = 0.0
        self._lock = asyncio.Lock()

    async def _refresh_keys(self, *, force: bool = False) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._retry_after:
                raise OidcProviderUnavailable("OIDC key retrieval is backing off")
            if force and now < self._next_unknown_kid_refresh:
                return
            if not force and now < self._expires_at:
                return
            if force:
                # Throttle *attempts*, including unsuccessful unknown-kid fetches.
                self._next_unknown_kid_refresh = now + 30.0
            try:
                # Stream bounded raw bytes without automatic decompression.
                # A provider ignoring identity encoding fails closed at JSON parse.
                async with self._client.stream(
                    "GET",
                    self._jwks_url,
                    headers={"Accept-Encoding": "identity", "Accept": "application/json"},
                    follow_redirects=False,
                    timeout=5.0,
                ) as response:
                    response.raise_for_status()
                    chunks = bytearray()
                    async for chunk in response.aiter_raw(chunk_size=8192):
                        if len(chunks) + len(chunk) > 65536:
                            raise ValueError("JWKS exceeds size limit")
                        chunks.extend(chunk)
                data = json.loads(chunks)
                if not isinstance(data, dict):
                    raise ValueError("invalid JWKS")
                keys = data.get("keys")
                if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
                    raise ValueError("invalid JWKS keys")
                trusted: dict[str, Any] = {}
                for item in keys:
                    if not isinstance(item, dict):
                        raise ValueError("invalid JWKS key")
                    if (
                        item.get("kty") != "RSA"
                        or item.get("alg", "RS256") != "RS256"
                        or item.get("use", "sig") != "sig"
                        or ("key_ops" in item and "verify" not in item["key_ops"])
                        or "d" in item
                    ):
                        continue
                    kid = item.get("kid")
                    if not isinstance(kid, str) or not 1 <= len(kid) <= 128:
                        continue
                    if kid in trusted:
                        raise ValueError("duplicate signing key identifier")
                    trusted[kid] = jwt.PyJWK.from_dict(item).key
                if not trusted:
                    raise ValueError("JWKS has no acceptable signing keys")
            except (httpx.HTTPError, ValueError, TypeError, KeyError, PyJWKError) as exc:
                # Prevent a down or malformed JWKS endpoint being hammered by
                # concurrent requests. Keep existing keys stale until refresh.
                self._retry_after = time.monotonic() + 5.0
                raise OidcProviderUnavailable("OIDC key retrieval failed") from exc
            self._keys = trusted
            self._expires_at = time.monotonic() + 300.0
            self._retry_after = 0.0

    async def verify(self, token: str) -> Principal:
        if not token or len(token) > 8192:
            raise InvalidOidcToken("Invalid access token")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise InvalidOidcToken("Unexpected signing algorithm")
            kid = header.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 128:
                raise InvalidOidcToken("Missing signing key")
            if time.monotonic() >= self._expires_at:
                await self._refresh_keys()
            if kid not in self._keys:
                await self._refresh_keys(force=True)
            key = self._keys.get(kid)
            if key is None:
                raise InvalidOidcToken("Unknown signing key")
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
                leeway=30,
            )
            sub = claims.get("sub")
            if not isinstance(sub, str) or not sub.strip() or len(sub) > 1024:
                raise InvalidOidcToken("Missing subject")
            return Principal(stable_subject_key(self._issuer, sub), "oidc_user")
        except (InvalidTokenError, ValueError, TypeError, KeyError) as exc:
            raise InvalidOidcToken("Invalid access token") from exc
