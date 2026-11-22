# OIDC browser login: Authorization Code + PKCE

This change connects EvidenceOS's Next.js backend-for-frontend (BFF) to the
cryptographic OIDC API verifier added in PR #18 and RBAC membership isolation
added in PR #17. It is an incremental integration, not a security certification.

## Setup

Use an OpenID Connect provider configured for a **confidential web client**
with Authorization Code flow and PKCE S256. Register the exact redirect URI:

`EVIDENCEOS_WEB_ORIGIN/auth/callback`

The frontend client ID is **not** the FastAPI resource audience. The provider
must issue **JWT access tokens** signed by the API's configured JWKS and carrying
the exact configured `EVIDENCEOS_OIDC_AUDIENCE`. Merely obtaining an ID token
for the web client is not sufficient.

Set the following in the root `.env` (never commit real values):

```dotenv
EVIDENCEOS_SECURITY_MODE=oidc
EVIDENCEOS_OIDC_ISSUER=https://your-provider.example/your-issuer
EVIDENCEOS_OIDC_JWKS_URL=https://your-provider.example/your-issuer/jwks
EVIDENCEOS_OIDC_AUDIENCE=evidenceos-api
EVIDENCEOS_OIDC_WEB_CLIENT_ID=your-web-client-id
EVIDENCEOS_OIDC_WEB_CLIENT_SECRET=your-confidential-web-client-secret
EVIDENCEOS_WEB_ORIGIN=http://127.0.0.1:3001
EVIDENCEOS_WEB_SESSION_KEY=generate-a-new-random-key
EVIDENCEOS_SESSION_REDIS_URL=redis://redis:6379
EVIDENCEOS_SESSION_REDIS_PASSWORD=a-unique-strong-32-plus-character-secret
```

Generate a new 32-byte random base64url key, for example:

```powershell
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

Use the printed value for `EVIDENCEOS_WEB_SESSION_KEY`. Generate an independent,
at-least-32-character Redis password. Redis is private to the Docker Compose
network and has no host port; this bundled Redis runs without persistence,
so a container restart safely invalidates all browser sessions. In production,
point `EVIDENCEOS_SESSION_REDIS_URL` to a managed `rediss://` TLS endpoint.
Any session key rotation invalidates all existing cookies. Never place the key in a GitHub issue,
screen recording or public deployment config.

Local `http://localhost` or `http://127.0.0.1` origins are permitted only
when `EVIDENCEOS_APP_ENV` is not `production`. Production configuration
requires HTTPS at a trusted external reverse proxy. The Docker Compose
ports remain bound to `127.0.0.1` by default.

Start:

```powershell
docker compose up --build -d
```

Then visit your exact `EVIDENCEOS_WEB_ORIGIN`; unauthenticated users are
redirected to `/signin`. Clicking **Sign in securely** initiates provider
authentication. `/auth/callback` exchanges the code, creates a server-encrypted
short-lived session, then redirects back to the workspace. The header contains
a POST-only **Sign out** action. Local and service-token modes remain intact.

## Security properties

- Maintained `openid-client` handles discovery, Authorization Code exchange,
  PKCE S256, authorization-response checks and ID token validation.
- A random `state`, `nonce` and code verifier are bound to the browser in a
  5-minute **encrypted HttpOnly, SameSite=Lax** transaction cookie.
- The ID token is never used as the API bearer token. Before creating a browser
  session, the BFF asks FastAPI to verify the **access token**, issuer,
  signature, expiry and API-specific audience. FastAPI continues verifying
  the token and project membership on every proxied request.
- Access tokens are stored only in an **AES-256-GCM encrypted HttpOnly**
  cookie. The key is kept on the Next.js server. No access or refresh token
  is returned to browser JavaScript or displayed in page HTML.
- Every cookie includes a cryptographically random, 256-bit session ID.
  Redis stores only a SHA-256 fingerprint of that ID, with a TTL never longer
  than the cookie. Every workspace request and backend API call checks the
  centralized record; logout atomically deletes it. Redis outages deny access,
  not bypass revocation.
- Session duration is capped to 10 minutes and shortened to the IdP token
  lifetime. There is **no silent refresh** and no refresh token storage.
- OIDC mode redirects unauthenticated HTML requests to login, returns 401
  for API requests, and rejects cross-origin state-changing API requests.
  Logout requires POST with an exact same-origin `Origin` header.
- All client-configured OIDC URLs and redirect origins are loaded from server
  environment variables, not request headers or query parameters.

## Limitations / mandatory follow-up

This milestone is **not sufficient for a general public internet launch**.
The browser session is **centrally revocable** through the Redis allowlist.
Local logout revokes all copies of that browser cookie after the Redis DELETE
succeeds. This does **not** revoke an independently stolen, raw JWT access
token against the FastAPI resource server; such a bearer token can remain
valid until its expiry or provider-side revocation. Also, already-in-flight
API requests may finish after logout. Provider SSO sessions are not ended by
local logout. For higher assurance, add token revocation/introspection as
supported by the provider, device/session inventory, anomaly detection,
IdP-specific token lifecycle policy, replay protection for OAuth transaction
cookies, and automated real-provider integration tests. Deploy only with
TLS, trusted proxy configuration, external rate limiting, CSP/security headers,
observability, and a dedicated security review.

Old projects without mapped owners remain inaccessible to OIDC users. Use a
separate explicitly authorized migration to allocate ownership; never assign
all projects automatically to the first account.

The web is a BFF, **not** a new identity provider. OIDC users cannot use
the old static service token as a shortcut. Existing local and service-token
modes continue only for the previous localhost single-operator workflow.

## Browser sign-out request and CSRF protection

The Sign out button submits an authenticated **same-origin fetch POST** to
`/auth/logout`. It sends the non-CORS-safelisted
`X-EvidenceOS-Logout: 1` header and follows the server's verified 303
redirect to `/signin`. The server validates the exact pinned
`EVIDENCEOS_WEB_ORIGIN` when the browser supplies `Origin`; if a browser
omits that header, it accepts the request only with the same-origin
`Sec-Fetch-Site` browser-generated metadata **and** the explicit custom
header. Cross-origin, `Origin: null`, untrusted origins, and bare form
POSTs are rejected. Plain GET navigation to `/auth/logout` is never a
valid logout action. Do not weaken this to accept arbitrary `Referer`,
`Host`, or `X-Forwarded-Host` values.

The browser navigates to the sign-in page only after a successful POST
redirect. An unreachable Redis session registry returns 503 and the UI
does **not** claim that session revocation succeeded. Logout revokes
this browser's Redis-backed session, not independently stolen raw JWTs
or the identity provider's global SSO session.
