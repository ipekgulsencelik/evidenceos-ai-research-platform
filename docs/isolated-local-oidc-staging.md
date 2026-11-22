# Isolated local OIDC staging (Windows / Docker Desktop)

**Purpose:** test genuine, two-user OIDC authorization without changing the
existing single-operator EvidenceOS installation. This is a *disposable local
development test*, not a production deployment. Everything here uses a
separate Compose project, PostgreSQL volume, Redis instance and Keycloak
realm. Existing `compose.yaml`, root `.env`, API port 8001, web port 3001,
and research data are never modified by these commands.

The Keycloak image is the official, pinned `26.8.2` release; it runs in
development mode bound to a localhost-only published port. Its data is not
production grade, and test credentials are kept only in untracked local files.

## 1. Install local development TLS once

From a PowerShell terminal in the repository root:

```powershell
winget install -e --id FiloSottile.mkcert
```

Restart the VS Code terminal if `mkcert` is not on PATH. **You must explicitly
approve adding the mkcert development CA to the Windows/browser trust
stores**. It changes your local trusted-root configuration:

```powershell
mkcert -install
```

For security, do not copy or share your mkcert `rootCA-key.pem`. This
setup copies *only the public root certificate* into the test directory.

## 2. Prepare a distinct test realm

```powershell
python scripts/prepare_oidc_staging.py
```

The script uses `mkcert` and generates:

- `.env.oidc-staging`: randomly generated database, Redis, confidential
  OIDC web client, Keycloak admin, session and two test-user secrets
- `staging/runtime/evidenceos-realm.json`: disposable Keycloak realm
  with two users (`e2e-owner`, `e2e-member`), a confidential web client
  and an **API-specific audience** protocol mapper
- `staging/runtime/idp.pem`, `idp-key.pem` and `rootCA.pem`:
  development TLS materials for `idp.localhost`

**All of these files are gitignored and must never be committed or sent in
screenshots.** The preparation script refuses to overwrite an existing
staging configuration. Never copy this file into the ordinary root `.env`.
Both test passwords are available privately in the generated environment
file for manual test login.

## 3. Start only the OIDC test stack

Run this exact command (do not omit `-f` or `--env-file`):

```powershell
docker compose --env-file .env.oidc-staging -f compose.oidc-staging.yaml up -d --build
```

The separate services are:

| Service | Local endpoint | Purpose |
| --- | --- | --- |
| Keycloak | `https://idp.localhost:8443` | Real OIDC issuer with TLS |
| Next.js test web | `http://127.0.0.1:3101` | Isolated browser BFF |
| FastAPI test API | `http://127.0.0.1:8101` | Real JWT/RBAC verifier |
| PostgreSQL | Unpublished | Dedicated research test database |
| Redis | Unpublished | Dedicated browser session allowlist |

The test web's HTTP origin is permitted **only for loopback, non-production
OIDC testing**. The identity provider itself remains HTTPS and both
containers validate its certificate against the generated, pinned
development CA. `idp.localhost` must resolve to loopback in the browser
and to the Keycloak network alias inside Docker. If resolution fails,
inspect Windows DNS/hosts configuration for `idp.localhost` only; do not
disable certificate verification.

The ordinary EvidenceOS remains available at
`http://127.0.0.1:3001`, with its existing data intact.

## 4. Check real TLS / OIDC discovery

Keycloak startup can take longer than the other containers. Inspect the
separate stack without revealing environment variables:

```powershell
docker compose --env-file .env.oidc-staging -f compose.oidc-staging.yaml ps
python scripts/check_oidc_staging.py
```

The preflight uses the local CA to verify the HTTPS issuer discovery
document and expected JWKS URL, then confirms the staging API and web
respond. **Preflight success is not the same as successful user login.**

To manually test the flow, open `http://127.0.0.1:3101`, choose **Sign in
securely**, then log in through the Keycloak test realm using one of the
generated test-user credentials. Create a disposable project, check
**Projects & members**, and verify that the signed-in project creator is
OWNER. Use the other test user to verify member access.

## 5. Run the two-user browser E2E suite

One-time Playwright installation in the new branch (after `npm ci`):

```powershell
cd apps/web
npm ci
npm install --no-save --package-lock=false @playwright/test@1.56.1
npx playwright install chromium
cd ../..
```

Then run from the repository root:

```powershell
python scripts/run_local_oidc_e2e.py
```

The launcher reads untracked local credentials into the test process
without printing them. It refuses any address other than
`http://127.0.0.1:3101`. The genuine Playwright browser suite verifies
two separate OIDC login sessions, JWT-backed identity, project isolation,
role grant/revoke, CSRF denial, session logout and replay rejection.

The E2E run **creates a test project in the isolated staging database**.
It does not read or modify your existing research projects. Re-running the
suite creates another disposable project in this separate database.

Note: the GitHub `oidc-e2e` workflow in
`docs/oidc-real-provider-e2e.md` targets a separately configured **HTTPS
remote staging** environment; it is not a substitute for this local test.

## 6. Shut down safely

To stop only the separate test stack (retain its data):

```powershell
docker compose --env-file .env.oidc-staging -f compose.oidc-staging.yaml down
```

To remove its separate disposable PostgreSQL volume too:

```powershell
docker compose --env-file .env.oidc-staging -f compose.oidc-staging.yaml down -v
```

The second command destroys **only the isolated staging volume**, not
the regular `evidenceos` project volume. To regenerate staging identities
and TLS files, stop the staging stack, delete only
`.env.oidc-staging` and `staging/runtime/`, then run the preparation
script again. Never use a bare `docker compose down -v` from the ordinary
configuration unless you deliberately intend to delete the primary database.

## Limits

- This tests local disposable OIDC sign-in only; Keycloak `start-dev` is
  not a secure production configuration.
- The test account passwords are intentionally kept in a local ignored
  file to support automation. Do not reuse passwords or secrets elsewhere.
- The test does not prove provider-wide logout or stolen **raw JWT**
  revocation; Redis revokes the *browser* session, not an independently
  exfiltrated bearer token.
- No automatic ownership migration for existing local research projects.
  Multi-user production migration needs an explicitly audited ownership plan.
- These files have configuration/unit tests in GitHub CI; a **real**
  Keycloak-in-Docker/browser E2E run must succeed on your computer before
  we can claim the whole flow works in the local environment.
