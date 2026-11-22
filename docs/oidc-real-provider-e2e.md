# Real OIDC provider end-to-end verification

This suite is **not a provider mock**. It drives the actual EvidenceOS Next.js
web application, its configured confidential OAuth2/OIDC client, its FastAPI
resource server, the PostgreSQL membership store, a Redis revocation store, and
an external identity provider using two dedicated **staging-only** accounts.

The ordinary GitHub PR CI verifies signed RS256 token validation, issuer and
API audience restrictions, membership isolation, browser boundary checks, and
the syntax of the browser suite. The **real provider browser test remains
unexecuted** until an administrator supplies a separate provider and test
accounts and explicitly runs the guarded workflow.

## Preflight: disposable staging

Provision an isolated staging deployment with a disposable PostgreSQL database
and separate Redis instance. The E2E test creates a new research project and
then grants and revokes access. It does **not** delete that project. **Never run
the E2E workflow against production or personal research data.**

Configure the application and identity provider:

- Use a real **HTTPS** issuer with OAuth2 Authorization Code, PKCE S256,
  `state`, `nonce`, and a confidential web client.
- Register the precise `https://STAGING_HOST/auth/callback` callback.
- Issue a signed **RS256 JWT access token** containing `iss`, `sub`,
  `iat`, `exp`, and the **API audience** in `aud`.
  The API audience must differ from the web client ID.
  Signing keys must be served at the API's pinned HTTPS JWKS URL.
- Configure `EVIDENCEOS_SECURITY_MODE=oidc`, `EVIDENCEOS_OIDC_ISSUER`,
  `EVIDENCEOS_OIDC_JWKS_URL`, `EVIDENCEOS_OIDC_AUDIENCE`,
  `EVIDENCEOS_OIDC_WEB_CLIENT_ID`, `EVIDENCEOS_OIDC_WEB_CLIENT_SECRET`,
  `EVIDENCEOS_WEB_ORIGIN`, `EVIDENCEOS_WEB_SESSION_KEY`,
  `EVIDENCEOS_SESSION_REDIS_URL`, and
  `EVIDENCEOS_SESSION_REDIS_PASSWORD` on the **server**, not in this repo.
- Provide two **dedicated, distinct** staging users with a straightforward
  form-based IdP login (`name="username"`, `type="password"` and a submit
  button). Use an account policy appropriate to an automated test tenant;
  never bypass the MFA policy of a production identity provider.
- Ensure the staging host is reachable from the Actions runner over trusted
  HTTPS with a valid certificate. Browser HTTPS validation is enabled.
  Private-only deployments should use an appropriately labeled private
  self-hosted runner and adjust the workflow's `runs-on` setting.

In GitHub, create and protect the **`oidc-e2e` Environment**. Add:

| Setting | Type | Purpose |
| --- | --- | --- |
| `EVIDENCEOS_E2E_ORIGIN` | Environment variable | Exact `https://staging.example` origin (no slash) |
| `EVIDENCEOS_E2E_USER_A` | Environment secret | First staging login |
| `EVIDENCEOS_E2E_PASSWORD_A` | Environment secret | First staging password |
| `EVIDENCEOS_E2E_USER_B` | Environment secret | Second staging login |
| `EVIDENCEOS_E2E_PASSWORD_B` | Environment secret | Second staging password |

No IdP client secret, JWT, user password, refresh token or browser session
should appear in GitHub logs, issues, or test artifacts. The suite disables
video, screenshots and traces; keep provider debugging logs off.

## Running

After this PR is merged (manual-dispatch workflows must be present on the
default branch), open **GitHub → Actions → OIDC browser E2E (disposable staging)
→ Run workflow**. Select the intended commit and explicitly check
**confirm_disposable_staging**. GitHub Environment protection can require an
additional reviewer approval.

For a private CI runner with Playwright already available, the same suite can
run locally from `apps/web` after setting the five
`EVIDENCEOS_E2E_*` environment variables (avoid adding them to committed files):

```powershell
npm ci
npm install --no-save --package-lock=false @playwright/test@1.56.1
npx playwright install chromium
npx playwright test --config playwright.staging.config.mjs
```

## Verified flows when the staging gate passes

1. Genuine provider sign-in and OAuth2 Authorization Code + PKCE exchange for
   two separate identities, including successful API JWT verification.
2. Verified distinct pseudonymous `/api/identity` keys.
3. Owner creates a project; other user cannot list or access it.
4. Forged `x-principal-key` and cross-origin project mutations cannot grant
   access.
5. Owner grants viewer, viewer gains READ but cannot manage memberships.
6. OWNER cannot be demoted through member management.
7. Owner revokes viewer; active viewer session immediately loses project access.
8. Sign out clears the browser session and revokes its Redis record. A copied
   encrypted cookie is rejected after logout, while the other authenticated
   user remains signed in.

The suite uses only project metadata endpoints and never submits sensitive
research papers to an LLM provider.

## Limits and production criteria

A green **ordinary CI** result is not a real IdP E2E result. Require an
explicitly green **OIDC browser E2E** run against disposable staging, then a
separate security review, TLS/reverse-proxy assessment, provider session and
token revocation analysis, recovery exercise, observability, rate limits,
identity-provider policy review, and ownership transfer policy before public
deployment.

This test does not assert that browser logout revokes an independently
exfiltrated raw JWT at the FastAPI resource server. Such JWTs stay valid
until their expiry or provider-side revocation. It also does not test IdP
global SSO logout, MFA, device session inventory, or concurrent ownership
transfer. Provider-specific login selectors may require adaptation in the
staging test; never weaken issuer, signature, audience or TLS validation
to accommodate a provider.
