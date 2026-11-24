# Privacy-minimized API request telemetry

**Scope:** observability foundation for the FastAPI service, not a
production monitoring, incident response or compliance certification.

## What is recorded

The existing server-generated `X-Request-ID` now correlates a single
completed FastAPI request to a structured JSON log written to stdout by
`evidenceos.http`. The event contains **only** these bounded fields:

```json
{"event":"http.request.completed","request_id":"<server-generated UUID>","method":"GET","route_group":"projects","status_code":200,"duration_ms":17}
```

The route group is assigned only after the framework has matched a
registered route, using fixed path-prefix comparisons; **only** the
fixed vocabulary is emitted: health, projects, academic, documents,
evidence, literature, other and unmatched. It never contains a literal project ID,
the raw URL or any user-provided value. Unknown HTTP methods are recorded
as `OTHER`. No success-level liveness/readiness noise is logged; failures
remain visible. Unhandled exceptions are counted as 500 without including
the traceback in this **structured event**.

**Never log:** authorization headers, JWTs, cookie values, OIDC codes,
database URLs, client IPs, query strings, PDF contents, prompts,
researcher notes, request bodies, response bodies or exception messages.
A caller-supplied `X-Request-ID` is ignored; the API generates a UUID.
The Docker API command disables Uvicorn's legacy access logs because
those can emit arbitrary request paths and query strings.

## Boundaries

- The new structured event has fixed fields; this does not sanitize all
  existing application or third-party diagnostics. A future review must
  inspect exception handlers, dependency logs, reverse proxies and the
  identity provider for separate sensitive-data disclosures.
- The readiness check now logs `health.database_unavailable` rather than
  a raw driver traceback. An error response remains `503` with a
  generic detail.
- `X-Request-ID` is currently issued by FastAPI. The Next.js BFF and
  ingress do not yet share the same identifier across the whole
  request chain; end-to-end trace propagation is **not** implemented.
- These are **logs**, not automatically collected Prometheus metrics,
  dashboards, traces or external alerts. The operator must configure a
  trusted collector and authorization/retention policies before production.
- Do not upload log bundles to public issue trackers. Set a retention
  period and a documented incident access process with appropriate
  controls over research-related operational metadata.

## Suggested next monitoring acceptance gates

1. Run structured logs from a disposable staging stack into an access-
   controlled collector; verify no secrets or query strings are included.
2. Observe 401/403 auth denials, 429/503 rate limiting/unavailable
   Redis, API 5xx, latency distributions and readiness failures.
3. Add actionable alerts based on representative traffic and SLOs;
   exercise one synthetic alarm without exposing credentials.
4. Correlate BFF + ingress + FastAPI with a single trusted request ID.
5. Run tests for data leakage in all first-party and third-party logs
   before processing sensitive material.

## Validation

From `apps/api`:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/test_observability.py
```

Full PR CI continues to run the existing Python, PostgreSQL, Redis,
Next.js and Docker checks. No schema migrations, project records, Redis
session data or local Keycloak credentials are changed by this milestone.

See [production readiness](production-readiness.md) for remaining gates.
