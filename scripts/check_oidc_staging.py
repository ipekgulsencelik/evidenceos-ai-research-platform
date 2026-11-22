"""Read-only checks for a disposable local Keycloak staging deployment."""
from __future__ import annotations

import json
import ssl
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
CA_FILE = ROOT / "staging" / "runtime" / "rootCA.pem"
ISSUER = "https://idp.localhost:8443/realms/evidenceos-staging"
JWKS = ISSUER + "/protocol/openid-connect/certs"


def fetch_json(url: str, *, context: ssl.SSLContext | None = None) -> dict:
    with urlopen(url, timeout=10, context=context) as response:  # noqa: S310
        if response.status != 200:
            raise ValueError("Unexpected response status")
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def main() -> int:
    if not CA_FILE.is_file():
        print("Missing local mkcert trust root; run preparation first.", file=sys.stderr)
        return 1
    try:
        trust = ssl.create_default_context(cafile=str(CA_FILE))
        metadata = fetch_json(ISSUER + "/.well-known/openid-configuration", context=trust)
        if metadata.get("issuer") != ISSUER or metadata.get("jwks_uri") != JWKS:
            raise ValueError("OIDC issuer or JWKS does not match the pinned trust anchors")
        if not str(metadata.get("authorization_endpoint", "")).startswith(ISSUER + "/"):
            raise ValueError("OIDC discovery produced an unexpected authorization endpoint")
        signing = fetch_json(JWKS, context=trust)
        keys = signing.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ValueError("OIDC JWKS returned no signing keys")
        with urlopen("http://127.0.0.1:8101/api/v1/health/live", timeout=10) as response:
            if response.status != 200:
                raise ValueError("Staging API is not healthy")
        with urlopen("http://127.0.0.1:3101/signin", timeout=10) as response:
            if response.status != 200:
                raise ValueError("Staging web sign-in is not responding")
    except (ValueError, OSError, URLError, HTTPError, json.JSONDecodeError) as exc:
        print(
            "OIDC staging verification failed. Inspect only the isolated staging "
            f"services and trusted certificate. Reason: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    print(
        "OK: separate OIDC staging issuer, pinned TLS trust, signing JWKS, "
        "API and web are reachable. This does NOT yet prove a browser login."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
