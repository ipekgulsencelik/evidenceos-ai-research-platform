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

First confirm that the standard Keycloak staging stack is healthy, and
that you are signed in at `http://127.0.0.1:3101/projects`. Keep the
browser session active.

```powershell
docker compose --env-file .env.oidc-staging -f compose.oidc-staging.yaml -f compose.oidc-rate-limit-test.yaml up -d --no-deps --force-recreate api
python scripts/check_oidc_staging.py
```

In that signed-in browser, open DevTools -> Console and execute:

```javascript
for (let i = 1; i <= 10; i++) {
  const response = await fetch("/api/projects", { cache: "no-store" });
  console.log(i, response.status, response.headers.get("Retry-After"));
}
```

Expected results: at least one HTTP `429` response with a **positive,
numeric** `Retry-After` header. Earlier responses should normally be
`200`, unless the verified user already consumed quota in the last
60 seconds. The browser API route must not expose Redis credentials or
Keycloak bearer tokens. This test only reads the user's project collection
and creates no new research projects.

For an independent quota-reset check, repeat the same read after the
first quota window expires. An admitted request should then return `200`
if the API and database are otherwise healthy.

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
