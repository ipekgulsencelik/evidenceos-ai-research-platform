# Distributed API rate limiting (authenticated research routes)

EvidenceOS applies a **shared Redis fixed-window** admission quota to
authenticated research requests, before database unit-of-work construction
or expensive provider operations. This is a production hardening control,
not a complete denial-of-service defense.

## Admission policy

- Every verified issuer-scoped `Principal.key` receives a global quota of
  **120 requests per 60-second window** by default.
- A subset of expensive POST/PUT operations (evidence assessment, PDF
  passage extraction, PDF analysis, semantic gaps and methodology review)
  also receives a narrower **12 requests per 60-second window** quota.
- Both quotas are checked and incremented by **one atomic Redis Lua
  operation**. Denied requests consume neither quota. Counters expire
  60 seconds after the first admitted request in each window.
- The only accepted quota identity is the **verified server-side
  principal**, never `X-Forwarded-For`, `x-principal-key`, untrusted user
  input, raw bearer token, or a query parameter. Redis keys contain only
  SHA-256 hashes of bucket labels and principal keys.
- Denied requests receive `429 Too Many Requests` with a whole-second
  `Retry-After` and `Cache-Control: no-store`. A Redis outage or
  malformed Redis response receives **503**, not unlimited access.
- Public liveness/readiness probes remain free of the authenticated quota.
  Unauthenticated API requests are rejected by the existing auth boundary
  before any rate-limit access.

## Configuration

Set these environment variables for a **production** API deployment:

```dotenv
EVIDENCEOS_RATE_LIMIT_ENABLED=true
EVIDENCEOS_RATE_LIMIT_REDIS_URL=rediss://your-private-managed-redis:6379
EVIDENCEOS_RATE_LIMIT_REDIS_PASSWORD=separate-32-plus-character-secret
EVIDENCEOS_RATE_LIMIT_REQUESTS_PER_MINUTE=120
EVIDENCEOS_RATE_LIMIT_EXPENSIVE_PER_MINUTE=12
```

Production settings **reject startup** if rate limiting is disabled,
the URL lacks TLS, a password is missing/weak, or the URL embeds a
username/password, fragment or query. The Redis service must be private,
TLS-verified using your deployment's trust store, and shared by **all API
replicas**. Quotas should be calibrated against realistic loads and
model-provider capacity before rollout. The development/test default is
`EVIDENCEOS_RATE_LIMIT_ENABLED=false`; the existing isolated OIDC
staging integration remains unchanged unless explicitly opted in.

Service-token mode deliberately shares its quota across all callers
using the same trusted service identity. OIDC users receive separate
issuer-scoped budgets.

## What is not covered

- This controls **authenticated FastAPI research requests only**.
  Unauthorized request floods, browser login attempts, upstream
  connection limits, global organization budgets, parallel in-flight
  work limits and bandwidth/upload throttling require ingress/WAF
  policies and additional controls. Do not expose FastAPI directly
  without a trusted TLS reverse proxy, strict request limits and
  appropriate DoS protections.
- Fixed windows permit bursts across window boundaries; this is a
  fairness baseline, not an exact sliding-window token bucket.
- Membership checks and RBAC still control which data a user may
  access; rate limiting does not replace authorization.
- Provider tokens can remain valid independently of EvidenceOS browser
  session revocation. Review provider-side revocation separately.

## Regression testing

- `uv run pytest tests/test_rate_limits.py`: configuration, verified
  identity buckets, health, fail-closed 503, quota 429 and Retry-After.
- GitHub Actions `quality` runs a real Redis instance with an
  isolated test-only password and executes
  `uv run pytest -m integration tests/test_rate_limit_redis.py`;
  concurrent requests through independent clients must admit exactly
  the configured quota.

Review production ingress limits and browser CSP separately.
