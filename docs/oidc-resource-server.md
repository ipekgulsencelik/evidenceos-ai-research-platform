# OIDC JWT resource-server verification (API-only milestone)

## Scope and deployment warning

This milestone adds **signature-verified JWT access-token authentication** to
FastAPI and binds authenticated users to the existing project RBAC introduced
in PR #17. It does **not** implement an OAuth2 authorization-code/PKCE login
flow, redirect callback, browser sessions, refresh-token management, MFA,
sign-out, or a complete public multi-user deployment.

When `EVIDENCEOS_SECURITY_MODE=oidc`, **the bundled Next.js workspace
deliberately responds HTTP 503**. The API may be tested independently, but
do not expose the API on the public internet or send confidential or
patient-identifiable research data until full security engineering is done.

The preexisting `local` and `service_token` modes are unchanged. The latter
is **an operator credential granting access to every project** and is not a
substitute for user authorization.

## Configuration

In the existing root `.env`, without overwriting your database or other
keys, configure:

```dotenv
EVIDENCEOS_SECURITY_MODE=oidc
EVIDENCEOS_OIDC_ISSUER=https://idp.example/tenant
EVIDENCEOS_OIDC_AUDIENCE=evidenceos-api
EVIDENCEOS_OIDC_JWKS_URL=https://idp.example/tenant/.well-known/jwks.json
```

Replace these **examples** with your actual identity provider's verified
values. Do not guess the JWKS URL: consult your provider's configuration.
Use a **distinct API resource audience**, never the public SPA's client ID,
to avoid mistakenly accepting an ID token as an API access token.

The API must receive an **asymmetrically signed JWT access token**, not a
reference/opaque token, login code or ID token. Issuer and audience must match
exactly. In OIDC mode the legacy static operator secret is **not accepted**.
No user identity is read from HTTP `X-User`, `X-Role`, or similar headers.

For temporary local API tests (only when the issuer is explicitly trusted):

```powershell
curl.exe -i http://localhost:8001/api/v1/health/live
curl.exe -i http://localhost:8001/api/v1/projects
```

The health probe remains public. The project listing responds 401 without a
valid Bearer token. A valid access token must originate from the configured
identity provider through an appropriate OAuth2 flow outside of EvidenceOS.
Do not paste a live access token into shell history, source control or
screenshots.

## What is verified

- JWT protected header must select `RS256` with a `kid` identifier;
  `none` or HMAC algorithms and unknown signing keys are rejected.
- The signing key is fetched from **one statically configured HTTPS JWKS URL**;
  token-provided key links (`jku`, `x5u`) are never consulted.
- JWKS retrieval disables redirects, limits the response size and keys, and
  caches keys for at most five minutes.
- The verifier validates signature, exact `iss`, configured API `aud`,
  `exp`, `iat`, optional `nbf`, and a nonempty string `sub`.
- Identity becomes a pseudonymous, issuer-scoped key used by database-backed
  project membership filtering, not a client-controlled account name.
- Untrusted, invalid or expired tokens return 401 without disclosing secrets.
  If trusted signing keys are unavailable, the API returns 503 rather than
  bypassing verification.

## Known limits / work remaining

A valid token **proves possession of the API access token** and the issuing
provider's signature, not that the browser implemented a secure sign-in
experience. Appropriate API scopes, authorized-client restrictions, token
revocation/short lifetimes, rate limits and abuse prevention are not yet
fully implemented. JWTs that have not expired may remain valid after external
logout unless additional session/revocation controls are added.

Existing projects lack migrated per-user ownership. In OIDC mode they will be
invisible to new users until an authenticated, explicitly authorized
migration or ownership-assignment workflow is added. **Never automatically
claim legacy projects on first login.** New projects are owned by the
verified token principal within the create transaction.

The access-decision history is pseudonymous and **not tamper-evident**.

Next milestones:
1. Trusted Authorization Code + PKCE with a standard, maintained web
   authentication library, server-side session management, secure HttpOnly
   cookies, TLS, and CSRF protection.
2. Explicit IdP-specific access-token profile/scope/authorized-client policy,
   key rotation resilience, logout/revocation and secret handling.
3. Owner-controlled membership administration and deliberate legacy ownership
   migration, with audit integrity and security review.

Never characterize this API-only milestone as enterprise-ready login or
multi-tenant production deployment.
