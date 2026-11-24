"""Bootstrap a disposable, isolated OIDC stack without modifying root .env.

Requires mkcert installed and its local CA trusted by the current user
(`mkcert -install` is a separate, explicit setup action).

Generated credentials, realm import and TLS private keys MUST remain untracked.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "staging" / "runtime"
ENV_FILE = ROOT / ".env.oidc-staging"
ISSUER = "https://idp.localhost:8443/realms/evidenceos-staging"
ORIGIN = "http://127.0.0.1:3101"
API_AUDIENCE = "evidenceos-api-staging"
CLIENT_ID = "evidenceos-web-staging"
POST_LOGOUT_RETURN = ORIGIN + "/signed-out"


def realm_config(client_secret: str, password_a: str, password_b: str) -> dict:
    return {
        "realm": "evidenceos-staging",
        "enabled": True,
        "displayName": "EvidenceOS isolated OIDC test realm",
        "sslRequired": "external",
        "accessTokenLifespan": 600,
        "ssoSessionIdleTimeout": 1800,
        "clients": [
            {
                "clientId": CLIENT_ID,
                "name": "Disposable EvidenceOS web test client",
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": False,
                "clientAuthenticatorType": "client-secret",
                "secret": client_secret,
                "standardFlowEnabled": True,
                "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": [ORIGIN + "/auth/callback"],
                "webOrigins": [ORIGIN],
                # Exact destination; never wildcard or unrelated trusted domain.
                "attributes": {"post.logout.redirect.uris": POST_LOGOUT_RETURN},
                "protocolMappers": [
                    {
                        "name": "api-audience",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-audience-mapper",
                        "consentRequired": False,
                        "config": {
                            "included.custom.audience": API_AUDIENCE,
                            "id.token.claim": "false",
                            "access.token.claim": "true",
                        },
                    },
                ],
            },
            {
                "clientId": API_AUDIENCE,
                "name": "EvidenceOS isolated test resource server",
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": True,
                "standardFlowEnabled": False,
                "directAccessGrantsEnabled": False,
            },
        ],
        "users": [
            {
                "username": "e2e-owner",
                "enabled": True,
                "emailVerified": True,
                "requiredActions": [],
                "credentials": [{"type": "password", "value": password_a, "temporary": False}],
            },
            {
                "username": "e2e-member",
                "enabled": True,
                "emailVerified": True,
                "requiredActions": [],
                "credentials": [{"type": "password", "value": password_b, "temporary": False}],
            },
        ],
    }


def main() -> int:
    if ENV_FILE.exists() or RUNTIME.exists():
        print(
            "Staging configuration already exists. No file was overwritten. "
            "Use the existing .env.oidc-staging or explicitly dismantle the "
            "isolated stack before provisioning a new one.",
            file=sys.stderr,
        )
        return 1

    mkcert = shutil.which("mkcert")
    if not mkcert:
        print("Install mkcert and run 'mkcert -install' explicitly first.", file=sys.stderr)
        return 1

    ca_root = subprocess.run(
        [mkcert, "-CAROOT"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    ca = Path(ca_root) / "rootCA.pem"
    if not ca.is_file():
        print("Trusted local mkcert CA not found; run 'mkcert -install'.", file=sys.stderr)
        return 1

    RUNTIME.mkdir(parents=True)
    try:
        subprocess.run(
            [
                mkcert,
                "-cert-file", str(RUNTIME / "idp.pem"),
                "-key-file", str(RUNTIME / "idp-key.pem"),
                "idp.localhost",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        shutil.copyfile(ca, RUNTIME / "rootCA.pem")
        password_a = secrets.token_urlsafe(27)
        password_b = secrets.token_urlsafe(27)
        client_secret = secrets.token_urlsafe(36)
        redis_password = secrets.token_urlsafe(36)
        database_password = secrets.token_urlsafe(36)
        admin_password = secrets.token_urlsafe(36)
        session_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        realm = realm_config(client_secret, password_a, password_b)
        (RUNTIME / "evidenceos-realm.json").write_text(
            json.dumps(realm, indent=2) + "\n", encoding="utf-8",
        )
        lines = [
            "# TEST ONLY. Keep this file untracked; do not copy into root .env.",
            "STAGING_POSTGRES_PASSWORD=" + database_password,
            "STAGING_REDIS_PASSWORD=" + redis_password,
            "STAGING_KEYCLOAK_ADMIN_PASSWORD=" + admin_password,
            "STAGING_OIDC_WEB_CLIENT_SECRET=" + client_secret,
            "STAGING_WEB_SESSION_KEY=" + session_key,
            "EVIDENCEOS_E2E_ORIGIN=" + ORIGIN,
            "EVIDENCEOS_E2E_USER_A=e2e-owner",
            "EVIDENCEOS_E2E_PASSWORD_A=" + password_a,
            "EVIDENCEOS_E2E_USER_B=e2e-member",
            "EVIDENCEOS_E2E_PASSWORD_B=" + password_b,
        ]
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if os.name == "posix":
            os.chmod(ENV_FILE, 0o600)
            os.chmod(RUNTIME / "evidenceos-realm.json", 0o600)
            os.chmod(RUNTIME / "idp-key.pem", 0o600)
    except Exception:
        # Never leave an incomplete staging secret on disk after failure.
        ENV_FILE.unlink(missing_ok=True)
        shutil.rmtree(RUNTIME, ignore_errors=True)
        raise

    print(
        "Isolated OIDC staging prepared: .env.oidc-staging and staging/runtime/. "
        "All generated passwords remain on disk and were not printed. "
        "Do not commit or share either path."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
