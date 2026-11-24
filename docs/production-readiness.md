# Production readiness: controlled pilot gate

**Status: NOT production approved.** EvidenceOS has a functional academic
research MVP and a validated **local**, isolated Keycloak/Redis staging
environment. Passing local E2E tests and repository CI does not establish
a secure publicly accessible production deployment. This document is a
readiness checklist, not a deployment approval or a substitute for a
professional security review.

## Implemented and demonstrated

- Python/FastAPI API, Next.js BFF, PostgreSQL/Alembic, Redis, Docker Compose.
- Verified OIDC Authorization Code + PKCE browser sign-in, independent
  JWT validation by the API, project-scoped RBAC and owner-managed membership.
- Centrally revocable browser sessions, CSRF defense, provider logout,
  pseudonymous project identities and a short cookie lifetime.
- Nonce-based **script** CSP, frame protection, no-sniff, referrer and
  permissions headers; HSTS configured for `EVIDENCEOS_APP_ENV=production`.
  The style CSP remains transitional (`style-src 'unsafe-inline'`).
- Shared authenticated API rate limiting: defaults 120 requests/minute and
  12 expensive operations/minute. API returns 429 and Retry-After; upstream
  503s fail closed. **Anonymous and ingress-level limits are not included.**
- Deterministic CI: Python Ruff, mypy, pytest (coverage minimum 80%),
  PostgreSQL integration, Redis atomic quota tests, TypeScript/Node tests,
  npm audit and API/web Docker builds.
- An operator-run disposable Keycloak browser E2E and Redis 429 acceptance
  flow have passed **locally**. These are not continuous production smoke
  tests.

## P0 — infrastructure and security controls (required before external pilot)

| Gate | Required evidence / acceptance | Current repository evidence |
| --- | --- | --- |
| Dedicated deployment | Select an isolated staging and production topology, service/DB/Redis sizing, owners and access boundaries; do not reuse disposable Keycloak staging | Not provisioned |
| HTTPS ingress | Trusted publicly valid TLS certificate, enforced HTTP→HTTPS redirect, only the reverse proxy exposes 443; internal API/DB/Redis are private; verify Host, forwarded-header trust and request body/time limits | Not implemented in repo |
| Browser security | Set exact HTTPS `EVIDENCEOS_WEB_ORIGIN`, protected cookies, CSP console audit on real deployed origin, HTTPS-only HSTS test; do not add `includeSubDomains` or preload before domain review | Local HTTP CSP and OIDC tests only |
| Identity provider | Dedicated production issuer and confidential client; exact callback and logout allowlist, MFA policy, account offboarding, signing-key rotation, issuer/JWKS pinning and token expiry/revocation strategy | Real local Keycloak E2E; operational policy unverified |
| Secrets | Store credentials in a secret manager / protected runtime injection. Rotate exposed staging credentials. No secrets in Git, images, issues, logs or screenshots; define rotation and incident response | Configuration validation exists; secret manager not selected |
| Shared stores | Private PostgreSQL and TLS-authenticated `rediss://` accessible to every API replica; independently provisioned protected session-Redis; connectivity, availability and credential rotation tested | Production rate limiter **requires** rediss; no production topology |
| Abuse controls | Network/ingress limits for anonymous traffic, login, connections, uploads, request size, timeouts and concurrency. App-level authenticated quota is not sufficient for DDoS defense | Not implemented |
| Data safety | Retention/classification policy; encryption at rest and in transit; explicit consent for external research providers; never use real patient-identifiable or confidential data before governance approval | Research and storage features available; policy missing |
| Release governance | Release tag, image provenance/scanning, reproducible deploy, migration rollback and no-downtime plan, manual promotion approval and deployment audit trail | CI available; deployment release process missing |

**Do not enable production just because** `EVIDENCEOS_APP_ENV=production`
passes startup validation. It checks selected credentials and URLs, not the
external TLS/network or organizational security posture. `compose.yaml`
is primarily for localhost development; it must not simply be exposed as a
public production topology.

## P1 — operations and recovery (required before sustained pilot)

| Gate | Required evidence / acceptance |
| --- | --- |
| Monitoring and alerting | FastAPI now emits privacy-minimized structured request events (see [observability foundation](api-observability-foundation.md)); cross-service request correlation, centralized log collection, error-rate/latency alerting, Redis/Postgres resource telemetry and upstream-provider monitoring remain unimplemented |
| Privacy-preserving audit | Least-privilege access to actor-attributed audit records; retention, export, tamper detection and log redaction; ensure JWTs, cookies, passwords and PDF text do not enter logs |
| Backup / disaster recovery | The [synthetic encrypted restore CI drill](disposable-postgres-recovery-drill.md) now validates migrations and source/target isolation. Real off-host backup retention, secrets/key management, production-like restore, **measured recovery RPO/RTO**, and lost-Redis procedures remain outstanding |
| Load / resilience | Realistic concurrent users and worst-case PDF/LLM request patterns, tail latency, 429 fairness, resource ceilings, provider outages and graceful recovery |
| Operations runbooks | On-call, deployment/rollback, outage response, credential rotation, IdP key rotation, backup restore and support escalation; dry-run each |
| Independent review | Threat model, security testing/penetration assessment, dependency/image audit, RBAC cross-tenant review, accessibility and compliance review |

## Existing local regression commands

From the repository root **against the disposable loopback stack only**:

```powershell
python scripts/check_oidc_staging.py
python scripts/run_local_oidc_e2e.py
```

The optional Redis quota acceptance test is **separate**. It requires the
`compose.oidc-rate-limit-test.yaml` override and a fresh Playwright
session. Always restore the default staging API afterwards; see
[OIDC rate-limit acceptance](oidc-rate-limit-acceptance.md). Never run
these E2E suites against actual customer or research data.

## Go / no-go

An external pilot may proceed only after P0 evidence is reviewed and
recorded, P1 operational safeguards appropriate to the pilot are exercised,
an accountable owner signs off, and no high/critical unresolved security
finding remains. Local browser regression success is a necessary check,
**not** a sufficient release decision.

## First implementation work items

1. Prepare a **deployment-specific HTTPS ingress design and test plan**
   (exact domain/provider/hosting topology required before enabling it).
2. Add ingress/anonymous rate limits and bounded upload/request budgets.
3. Establish structured operational telemetry and alerting without secrets.
4. Create repeatable encrypted backup/restore exercises with measured RPO/RTO.
5. Establish pilot deployment and rollback gates in CI/CD.

Reference: [OIDC real-provider E2E](oidc-real-provider-e2e.md),
[browser security headers](browser-security-headers.md),
[API shared rate limits](api-distributed-rate-limits.md).
