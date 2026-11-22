# Security Foundation — protected local single-operator mode

## Scope

This change adds a **first security boundary**, not full user identity, RBAC,
project membership, multi-tenant isolation or enterprise SSO. The system
remains a localhost-only research prototype. **Do not expose it to the public
internet or use it with sensitive, confidential or patient-identifiable data.**

The existing development workflow stays unchanged until protection is enabled.

## Two distinct credentials

1. **Web entrypoint:** Next.js 16 request proxy requires HTTP Basic credentials
   for every page and API route (except public static assets). This is suitable
   **only for loopback/local development**; HTTP Basic must never be used on an
   unencrypted public connection. There are no login sessions, account recovery,
   rate limits, MFA or per-user identities.
2. **Internal API:** FastAPI requires a server-to-server Bearer secret for every
   research router; only health/live and health/ready remain public. The browser
   must never receive this API secret. The Next.js server supplies it from its
   environment to backend calls. Credentials are verified using constant-time
   digest comparisons and are not logged.

A static token grants access to **every** project. This is an interim
single-operator safeguard and does not protect projects from another operator
who knows the credential.

## Enable on Windows using Docker Compose

Do not overwrite an existing `.env` that contains database or external API keys.
Make a backup and add these entries to the existing `.env` file:

```dotenv
EVIDENCEOS_APP_ENV=development
EVIDENCEOS_SECURITY_MODE=service_token
EVIDENCEOS_API_SERVICE_TOKEN=<random server secret of at least 32 characters>
EVIDENCEOS_WEB_USERNAME=research-admin
EVIDENCEOS_WEB_PASSWORD=<different passphrase of at least 20 characters>
```

Generate two independent high-entropy secrets locally (PowerShell):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build -d
docker compose ps
```

Use the first value as `EVIDENCEOS_API_SERVICE_TOKEN`, the second as
`EVIDENCEOS_WEB_PASSWORD`. Do **not** commit the actual values, paste them
into tickets/logs or set them as `NEXT_PUBLIC_` variables.

Open http://localhost:3001 and enter the web credentials when the browser
prompts. Requests through Next.js carry the server-side API secret.

`EVIDENCEOS_APP_ENV=production` requires protected `service_token` mode; the
backend refuses to start if absent or if the token is shorter than 32
characters. Next.js returns 503 when protected credentials are missing. Docker
health checks accept the web's expected 401 challenge in protected mode, but
do not accept a misconfiguration 503.

## API verification (localhost only)

With protected mode, request without a credential:

```powershell
curl.exe -i http://localhost:8001/api/v1/projects
```

Expected: `401`, generic `Authentication required`, and
`WWW-Authenticate: Bearer`. An authorized request with a configured bearer
token can use the API; do not put tokens in shell history or share screenshots
that include an authorization header. The `/api/v1/health/live` endpoint stays
public for infrastructure liveness.

## Architectural boundary

- Settings validate required security configuration and fail closed for
  production. The default `local` mode is intentionally not secure.
- FastAPI composition attaches a reusable credential dependency to all
  research routers, excluding the explicitly public health router.
- Next.js has a web request boundary and server-only API token transport.
- The original PostgreSQL schema, projects, PDF evidence, revisions and
  migrations remain unchanged.
- Tests cover anonymous/invalid authorization, local compatibility,
  successful protected requests, missing/weak production secrets and
  selection of security mode.

A generic request ID and limited warning log for rejected service credentials
are available, but these are **not** tamper-evident, user-attributed audit
records.

## Required before any true production rollout

- OIDC/OAuth2 with robust server-side sessions, MFA and account lifecycle;
- database-backed organizations, project ownership and membership, enforced
  by use cases and SQL queries, not only URL checks;
- per-project role policies (owner/editor/reviewer/viewer), denial tests,
  least privilege and migration strategy for existing unowned projects;
- append-only, actor-attributed, access-controlled and retained audit events;
- TLS termination, secure cookies, CSRF protection, rate limiting, abuse
  controls, secret rotation, secure backup/recovery and deployment hardening;
- security review and penetration tests.

**This milestone is not enterprise-ready authentication or authorization.**
