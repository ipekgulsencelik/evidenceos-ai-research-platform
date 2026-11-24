# Safe local OIDC API quota verification

This opt-in check exercises the genuine Keycloak browser session and an
actual shared Redis-backed FastAPI rate limiter in the **disposable local**
`evidenceos-oidc-staging` project. It does not use production credentials,
publish a new host port, or delete volumes.

The standard local staging Compose keeps API rate limiting disabled by
default; the test override enables a small `6/minute` quota only on the
existing staging API. Do not run the normal OIDC E2E suite during this test:
that suite intentionally performs more operations and may be throttled.

## Run from repository root

First confirm the standard Keycloak staging stack is healthy. The test
creates **its own fresh browser login** and does not depend on how long the
user's Chrome session has been open. The EvidenceOS browser session lasts
at most ten minutes, so a long-lived manual DevTools tab can return
`401 Unauthorized` before reaching the quota.

```powershell
docker compose --env-file .env.oidc-staging -f compose.oidc-staging.yaml -f compose.oidc-rate-limit-test.yaml up -d --no-deps --force-recreate api
python scripts/check_oidc_staging.py
python scripts/run_local_oidc_rate_limit_e2e.py
```

Expected: Playwright reports `1 passed`, and logs only HTTP status codes,
including `429` with a positive numeric `Retry-After` header.
It uses an existing **staging-only** Keycloak identity from the untracked
`.env.oidc-staging`; credentials are not printed or persisted. The
real OIDC callback validates the API token first, and the automated
browser immediately exercises the BFF and Redis quota before the new
cookie expires. Prior use of the same test identity in the preceding
minute may reduce the number of successful `200` responses.

If Playwright is missing in `apps/web`, install the locally tested version
there before launching the script:

```powershell
cd apps/web
npm install --no-save --package-lock=false @playwright/test@1.60.0
npx playwright install chromium
cd ../..
```

The manual Chrome Console loop remains an optional debugging method, but
an expired session cannot demonstrate rate limiting. Do not interpret ten
consecutive `401` statuses as a Redis rate-limit failure.

## Always restore the original staging configuration

```powershell
docker compose --env-file .env.oidc-staging -f compose.oidc-staging.yaml up -d --no-deps --force-recreate api
python scripts/check_oidc_staging.py
python scripts/run_local_oidc_e2e.py
```

This removes the temporary test-only limit settings without wiping the
database or touching the existing Redis session allowlist.

## Limits

- A `429` on this path confirms real browser -> Next.js BFF ->
  authenticated FastAPI -> Redis rate limiting. It is not a load test,
  production DDoS guarantee or external ingress/WAF policy check.
- The default production configuration requires a **TLS-protected**
  dedicated/shared Redis service using `rediss://` and a strong secret.
  Do not reuse this staging Compose override in production.
- FastAPI's 429/503 `Retry-After` was previously dropped by the BFF.
  This change only forwards a strictly validated, bounded numeric delay
  on those statuses; arbitrary upstream headers are not reflected.
