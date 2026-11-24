"""One-time, idempotent post-logout URI registration in EXISTING local Keycloak.

Target is intentionally hard-coded to the isolated localhost staging realm.
This never recreates Keycloak, passwords, users, TLS, or PostgreSQL volumes.
The development admin credential is read from an untracked local file;
no credentials, ID tokens or API response bodies are printed.
"""
from __future__ import annotations

import json
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from prepare_oidc_staging import (
    CLIENT_ID, ENV_FILE, ORIGIN, POST_LOGOUT_RETURN, RUNTIME,
)

ADMIN_BASE = "https://idp.localhost:8443"
REALM = "evidenceos-staging"
CA_FILE = RUNTIME / "rootCA.pem"


def updated_client(existing: dict[str, Any]) -> dict[str, Any]:
    """Preserve all existing client fields, updating only the exact logout URI."""
    if (existing.get("clientId") != CLIENT_ID or
            existing.get("protocol") != "openid-connect" or
            existing.get("publicClient") is not False or
            not isinstance(existing.get("id"), str) or
            not existing["id"] or
            ORIGIN + "/auth/callback" not in existing.get("redirectUris", [])):
        raise ValueError("Refusing to edit a client other than isolated staging web OIDC")
    attrs = existing.get("attributes")
    if attrs is not None and not isinstance(attrs, dict):
        raise ValueError("Invalid OIDC client attributes")
    result = dict(existing)
    result["attributes"] = {**(attrs or {}), "post.logout.redirect.uris": POST_LOGOUT_RETURN}
    return result


def admin_password() -> str:
    # Only a fixed, untracked staging environment file is accepted.
    if not ENV_FILE.is_file():
        raise ValueError("Missing .env.oidc-staging: do not regenerate existing credentials")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name == "STAGING_KEYCLOAK_ADMIN_PASSWORD" and len(value) >= 32:
            return value
    raise ValueError("Missing existing isolated staging admin credential")


def read_json(request: Request, trust: ssl.SSLContext) -> Any:
    with urlopen(request, context=trust, timeout=10) as response:
        return json.load(response)


def main() -> int:
    try:
        if not CA_FILE.is_file():
            raise ValueError("Local staging CA missing; do not recreate secrets")
        trust = ssl.create_default_context(cafile=str(CA_FILE))
        token = read_json(Request(
            ADMIN_BASE + "/realms/master/protocol/openid-connect/token",
            data=urlencode({
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "staging-admin",
                "password": admin_password(),
            }).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        ), trust)
        bearer = token.get("access_token") if isinstance(token, dict) else None
        if not isinstance(bearer, str) or not bearer:
            raise ValueError("Staging administrator authentication did not return an access token")

        base = ADMIN_BASE + "/admin/realms/" + REALM + "/clients"
        auth = {"Authorization": "Bearer " + bearer}
        found = read_json(Request(
            base + "?" + urlencode({"clientId": CLIENT_ID}), headers=auth,
        ), trust)
        if not isinstance(found, list) or len(found) != 1:
            raise ValueError("Expected exactly one isolated staging OIDC web client")
        candidate = found[0]
        if not isinstance(candidate, dict) or candidate.get("clientId") != CLIENT_ID:
            raise ValueError("Unexpected Keycloak client")
        identifier = candidate.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Missing staging client identifier")
        client_url = base + "/" + quote(identifier, safe="")
        existing = read_json(Request(client_url, headers=auth), trust)
        if not isinstance(existing, dict):
            raise ValueError("Invalid staging client response")
        updated = updated_client(existing)

        if updated == existing:
            print("OIDC staging post-logout URI already registered; no change required.")
            return 0

        with urlopen(Request(
            client_url,
            data=json.dumps(updated).encode("utf-8"),
            headers={**auth, "Content-Type": "application/json"},
            method="PUT",
        ), context=trust, timeout=10) as response:
            if response.status not in (200, 204):
                raise ValueError("Failed to update staging client")
        verified = read_json(Request(client_url, headers=auth), trust)
        if not isinstance(verified, dict) or verified.get("attributes", {}).get(
                "post.logout.redirect.uris") != POST_LOGOUT_RETURN:
            raise ValueError("Post-logout redirect registration could not be verified")
    except (ValueError, OSError, HTTPError, URLError, json.JSONDecodeError, KeyError, TypeError) as exc:
        # Do not print exception content; providers can include sensitive details.
        print(
            "OIDC staging logout configuration failed: " + type(exc).__name__
            + ". Confirm the isolated Keycloak is ready and the existing "
            "staging admin credentials are valid.",
            file=sys.stderr,
        )
        return 1

    print("OK: exact EvidenceOS signed-out return registered in isolated Keycloak.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
