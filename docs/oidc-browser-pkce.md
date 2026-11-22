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
```

Generate a new 32-byte random base64url key, for example:

```powershell
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

Use the printed value for `EVIDENCEOS_WEB_SESSION_KEY`. Any key rotation
invalidates all existing sessions. Never place the key in a GitHub issue,
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
- Session duration is capped to 10 minutes and shortened to the IdP token
  lifetime. There is **no silent refresh** and no refresh token storage.
- OIDC mode redirects unauthenticated HTML requests to login, returns 401
  for API requests, and rejects cross-origin state-changing API requests.
  Logout requires POST with an exact same-origin `Origin` header.
- All client-configured OIDC URLs and redirect origins are loaded from server
  environment variables, not request headers or query parameters.

## Limitations / mandatory follow-up

This milestone is **not sufficient for a general public internet launch**.
The encrypted session is **stateless**; clearing cookies on logout does not
invalidate stolen copies until their short expiry. Provider SSO sessions are
not ended by local logout. For higher assurance, add server-side revocation,
device/session inventory, session anomaly detection, centralized logout,
IdP-specific token lifecycle policy, replay protection for OAuth transaction
cookies, and automated identity-provider integration tests. Deploy only with
TLS, trusted proxy configuration, external rate limiting, CSP/security headers,
observability, and a dedicated security review.

Old projects without mapped owners remain inaccessible to OIDC users. Use a
separate explicitly authorized migration to allocate ownership; never assign
all projects automatically to the first account.

The web is a BFF, **not** a new identity provider. OIDC users cannot use
the old static service token as a shortcut. Existing local and service-token
modes continue only for the previous localhost single-operator workflow.
