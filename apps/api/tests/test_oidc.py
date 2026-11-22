"""No-network OIDC access token verification and RBAC integration regression tests."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from pydantic import ValidationError

from evidenceos.domain.entities.access import stable_subject_key
from evidenceos.domain.entities.project import ResearchProject
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.oidc import (
    InvalidOidcToken,
    OidcAccessTokenVerifier,
    OidcProviderUnavailable,
)
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from tests.fakes import FakeAccessAuditRepository, FakeMembershipRepository, FakeUnitOfWork

ISSUER = "https://idp.example/tenant"
AUDIENCE = "evidenceos-api"
JWKS_URL = "https://idp.example/tenant/jwks"
DATABASE = "postgresql+asyncpg://u:p@localhost:5432/test"


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def jwks(private_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    key = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    key.update({"kid": "primary", "use": "sig", "alg": "RS256"})
    return {"keys": [key]}


def oidc_settings(**overrides: str) -> Settings:
    values: dict[str, str] = {
        "app_env": "test",
        "database_url": DATABASE,
        "security_mode": "oidc",
        "oidc_issuer": ISSUER,
        "oidc_audience": AUDIENCE,
        "oidc_jwks_url": JWKS_URL,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def signed_token(
    key: rsa.RSAPrivateKey,
    changes: dict[str, Any] | None = None,
    *,
    kid: str = "primary",
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "researcher-123",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(changes or {})
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def mock_client(
    jwks: dict[str, Any], *,
    status: int = 200,
    calls: list[str] | None = None,
) -> httpx.AsyncClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        assert str(request.url) == JWKS_URL
        return httpx.Response(status, json=jwks)
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


@pytest.mark.parametrize(
    "changes",
    [
        {"oidc_audience": ""},
        {"oidc_issuer": ""},
        {"oidc_jwks_url": ""},
        {"oidc_issuer": "http://idp.example"},
        {"oidc_jwks_url": "http://idp.example/keys"},
        {"oidc_jwks_url": "https://someone@idp.example/keys"},
        {"oidc_jwks_url": "https://idp.example/keys#attack"},
    ],
)
def test_oidc_configuration_rejects_missing_or_unsafe_trust_anchors(
    changes: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        oidc_settings(**changes)


def test_oidc_mode_allows_pinned_production_configuration() -> None:
    config = oidc_settings(app_env="production")
    assert config.security_mode == "oidc"


@pytest.mark.asyncio
async def test_valid_signed_access_token_maps_to_scoped_principal(
    private_key: rsa.RSAPrivateKey, jwks: dict[str, Any],
) -> None:
    calls: list[str] = []
    async with mock_client(jwks, calls=calls) as client:
        verifier = OidcAccessTokenVerifier(oidc_settings(), client)
        first = await verifier.verify(signed_token(private_key))
        second = await verifier.verify(signed_token(private_key))
    assert first.kind == "oidc_user"
    assert first.key == stable_subject_key(ISSUER, "researcher-123")
    assert second == first
    assert calls == [JWKS_URL]


@pytest.mark.parametrize(
    "invalid_claims",
    [
        {"iss": "https://another.example"},
        {"aud": "some-other-api"},
        {"sub": ""},
        {"sub": 42},
        {"exp": datetime(2020, 1, 1, tzinfo=UTC)},
        {"nbf": datetime.now(UTC) + timedelta(hours=1)},
        {"iat": datetime.now(UTC) + timedelta(hours=1)},
    ],
)
@pytest.mark.asyncio
async def test_invalid_identity_claims_are_rejected(
    private_key: rsa.RSAPrivateKey, jwks: dict[str, Any],
    invalid_claims: dict[str, Any],
) -> None:
    async with mock_client(jwks) as client:
        verifier = OidcAccessTokenVerifier(oidc_settings(), client)
        with pytest.raises(InvalidOidcToken):
            await verifier.verify(signed_token(private_key, invalid_claims))


@pytest.mark.asyncio
async def test_rejects_untrusted_keys_algorithms_and_malformed_tokens(
    private_key: rsa.RSAPrivateKey, jwks: dict[str, Any],
) -> None:
    untrusted = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tokens = [
        signed_token(private_key, kid="unknown"),
        signed_token(untrusted),
        jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": "bad"},
            "not-a-trusted-key",
            algorithm="HS256",
            headers={"kid": "primary"},
        ),
        "not-a-jwt",
        "a" * 8200,
    ]
    async with mock_client(jwks) as client:
        verifier = OidcAccessTokenVerifier(oidc_settings(), client)
        for token in tokens:
            with pytest.raises(InvalidOidcToken):
                await verifier.verify(token)


@pytest.mark.asyncio
async def test_expiry_is_required_even_for_valid_signature(
    private_key: rsa.RSAPrivateKey, jwks: dict[str, Any],
) -> None:
    now = datetime.now(UTC)
    missing_exp = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "researcher", "iat": now},
        private_key, algorithm="RS256", headers={"kid": "primary"},
    )
    async with mock_client(jwks) as client:
        with pytest.raises(InvalidOidcToken):
            await OidcAccessTokenVerifier(oidc_settings(), client).verify(missing_exp)


@pytest.mark.parametrize(
    "bad_jwks",
    [
        {"keys": []},
        {"keys": "not-an-array"},
        {"keys": [{"kid": "hmac", "kty": "oct", "k": "fake"}]},
    ],
)
@pytest.mark.asyncio
async def test_unusable_jwks_causes_fail_closed_unavailable(
    private_key: rsa.RSAPrivateKey, bad_jwks: dict[str, Any],
) -> None:
    async with mock_client(bad_jwks) as client:
        with pytest.raises(OidcProviderUnavailable):
            await OidcAccessTokenVerifier(oidc_settings(), client).verify(
                signed_token(private_key)
            )


def test_oidc_access_token_is_required_and_project_membership_is_enforced(
    private_key: rsa.RSAPrivateKey, jwks: dict[str, Any],
) -> None:
    settings = oidc_settings()
    app = create_app(settings)
    projects: dict[UUID, ResearchProject] = {}
    memberships = FakeMembershipRepository()
    audits = FakeAccessAuditRepository()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, memberships=memberships, access_audit=audits)

    app.dependency_overrides[get_uow_factory] = lambda: factory
    token = signed_token(private_key)
    other = signed_token(private_key, {"sub": "other-researcher"})

    with TestClient(app) as test_client:
        # Replace managed real transport with deterministic, offline JWKS.
        app.state.oidc_verifier = OidcAccessTokenVerifier(
            settings, mock_client(jwks)
        )
        assert test_client.get("/api/v1/projects").status_code == 401
        assert test_client.get(
            "/api/v1/projects", headers={"Authorization": "Bearer not-a-jwt"}
        ).status_code == 401
        owned = test_client.post(
            "/api/v1/projects",
            json={"title": "Owned OIDC project", "domain": "academic"},
            headers={"Authorization": "Bearer " + token},
        )
        assert owned.status_code == 201, owned.text
        project_id = owned.json()["id"]
        assert test_client.get(
            "/api/v1/projects", headers={"Authorization": "Bearer " + token}
        ).json()[0]["id"] == project_id
        assert test_client.get(
            f"/api/v1/projects/{project_id}",
            headers={"Authorization": "Bearer " + other},
        ).status_code == 404
        assert test_client.get(
            "/api/v1/projects", headers={"Authorization": "Bearer " + other}
        ).json() == []
    assert any(a.outcome == "denied" for a in audits.events)
