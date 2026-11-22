# EvidenceOS — Research Intelligence Platform

EvidenceOS combines source-backed academic research and DOI bibliographic checking. **The current implementation includes a functional academic search API and a web workspace.** Legal research, full-text scientific claim verification, and advanced AI analysis are future work.

## Stack

Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Alembic / uv, Next.js 16 / React 19 / TypeScript / Tailwind CSS 4, Docker Compose, GitHub Actions, Ruff, mypy, pytest, Node unit tests.

## Start locally on Windows (Docker Desktop)

From repository root:

```powershell
Copy-Item .env.example .env # only if .env is not already present; preserves your existing OpenAlex key
# Edit .env and set EVIDENCEOS_OPENALEX_API_KEY using https://openalex.org/settings/api
docker compose up --build -d
docker compose ps
```

- **Research UI:** http://localhost:3001
- **FastAPI Swagger:** http://localhost:8001/docs
- API liveness: http://localhost:8001/api/v1/health/live

Host ports may already be used by other projects. Change `EVIDENCEOS_WEB_HOST_PORT=3002` or `EVIDENCEOS_API_HOST_PORT=8002` in root `.env` if necessary, then run `docker compose up -d --force-recreate web api`. The API container always uses port 8000 internally and the web container port 3000. PostgreSQL is not exposed to the host; Docker services connect to `db:5432`.

**IMPORTANT:** Do not overwrite your existing `.env` if it contains your working OpenAlex key. Never commit `.env`. Do not use `docker compose down -v` unless you intend to delete the database volume.

## Web app

`apps/web/` is a Next.js App Router UI with two implemented features:

1. OpenAlex academic search with up to 25 results, author/year/DOI/source metadata.
2. Crossref DOI metadata validation, including exact title comparisons and unverified/mismatch states.

The UI uses Next.js same-origin API routes to proxy to FastAPI, so browser code never sees API credentials or the private Docker API hostname. Set `BACKEND_API_URL` **server-side only** for local Next.js development (Docker sets it automatically to `http://api:8000`). See [`apps/web/README.md`](apps/web/README.md).

## API endpoints

| Method | Route | Function |
|---|---|---|
| GET | `/api/v1/health/live` | API process liveness |
| GET | `/api/v1/health/ready` | Database readiness |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects/{id}` | Read project |
| GET | `/api/v1/academic/works?query=...&limit=10` | OpenAlex metadata search |
| POST | `/api/v1/academic/citations/verify` | Crossref DOI metadata comparison |

A `verified` DOI status means Crossref has matching bibliographic metadata, **not** that a paper's claims are valid. `not_found_in_crossref` does not rule out another DOI registration agency.

## Quality and architecture

The backend uses Clean Architecture: `domain <- application <- presentation` with the infrastructure adapters implementing domain ports and dependency composition at the API edge. The web application has separate typed API contracts, validation, route handlers, components, and server-side outbound communication.

GitHub Actions runs backend lint, strict typing, coverage, PostgreSQL integration, frontend TypeScript/tests/build, and container builds.

## Operational and security limitations

This software is an **early-stage development system**. It does not yet include authentication, authorization, RBAC, tenant isolation, public rate limiting, security reviews, audit logs, or legal counsel signoff. **Do not publish the web or API service to the internet or process sensitive customer data.** Web and API host ports bind to `127.0.0.1` for local use. OpenAlex and Crossref are external dependencies whose data access and usage terms must be respected.

Web dependency versions are pinned by the committed `apps/web/package-lock.json`; CI and Docker use `npm ci` to install reproducibly.

## Phase 2.1 — Local PDF passage retrieval

EvidenceOS now imports a selectable-text PDF (8 MiB / 30-page maximum), retrieves
page-grounded candidate excerpts with deterministic keyword overlap and lets
researchers insert chosen excerpts into the existing AI assessment form.
PDF upload does not invoke Groq. Only explicit assessment sends selected passages.
No OCR, persistent PDF storage, or scientific claim-support guarantees.
See docs/pdf-document-intelligence.md for boundaries and limitations.

## Scientific Literature Intelligence

New: consent-based AI extraction of research aim, design, participants,
instruments, findings and limitations from a PDF. Each included field must
have an exact quote from a selected original page. Compare up to five
documents and export CSV. Manual scientific verification is still required.
Details: docs/scientific-literature-intelligence.md.


## Scientific literature review-quality update

The six-field extraction matrix now has search, field/status filters,
page-grounded quote status explanations and separate reviewer annotations,
with safe CSV export. Model quotes that cannot be verified are not displayed
as evidence. See docs/literature-review-quality.md.


## Research Workspace & Literature Management

Academic projects can now persist server-generated literature analyses and
append-only reviewer revisions in PostgreSQL. PDF binaries are not saved.
Requires the additive 0002 Alembic migration (Docker Compose handles it).
This is localhost-only: no authentication or access control. See
docs/research-workspace.md for workflow, privacy limits and API contracts.


## Research Library and Evidence Coverage Comparison

Within a selected academic project, Research Library lets you search the
newest 100 saved analysis snapshots, add persisted tags/reading statuses,
and compare 2–10 distinct PDFs using source-quoted extracted fields.
The "gap" output is a **manual verification candidate**, not a scientific
claim that the literature lacks evidence. No extra AI call is made by the
comparison. Migration 0003 adds metadata without altering existing records.
See docs/research-library-gap-analysis.md for scope and privacy limits.


## Semantic Research Gap Intelligence (preview)

Optional consent-gated Groq comparison of populations, study designs, scales and findings from saved source quotations in **2–10 different PDFs**. Every source reference is checked on the backend and tentative findings are labeled for manual review. No claims of proven scientific novelty. No PDF binaries are sent. See `docs/semantic-research-gap-intelligence.md`.


## Research Methodology Intelligence — source-limited preview

Choose a saved academic literature record and, with separate consent, request a
Groq-assisted review of seven methodology reporting dimensions. Model notes are
linked only to preverified quotations and page locators; unsupported facets
are marked **not assessable**. This is not scientific quality scoring or full-paper
review. No new database migration is required. Details:
`docs/research-methodology-intelligence.md`.


## Research Quality & Bias Intelligence (human-review preview)

A seven-item **source coverage + manual reporting and possible-concern**
checklist for one saved academic analysis. Reviewer judgments are explicitly
self-attested as checked against the original full PDF, stored as append-only
PostgreSQL revisions by Alembic 0004, and shown separately from immutable
AI evidence. This is **not a validated risk-of-bias tool or automatic quality
score**. See `docs/research-quality-bias-intelligence.md`.

## Security Foundation — protected local single-operator mode

Optional `EVIDENCEOS_SECURITY_MODE=service_token` adds a Bearer credential gate
to all research API endpoints and a separate HTTP Basic gate for the localhost
web workspace. The web server forwards the internal token without exposing it
to the browser. Production configuration fails closed if the service token is
missing or too short; health probes remain unauthenticated.

**This is not user authentication, project-level authorization, RBAC, or
tamper-evident auditing.** The default local mode remains unprotected.
Do not deploy this single-operator proof of concept to the public internet.

Configuration, migration-safe instructions, validation, and remaining security
work: [Security Foundation](docs/security-foundation.md).

## Project RBAC and access-decision audit foundation

An additive Alembic **0005** migration defines project membership roles
(owner/editor/reviewer/viewer), project-aware authorization policies, scoped
project listings and pseudonymous access-decision records. In future OIDC
mode, legacy projects will **not** be implicitly claimed by a new user.
Current local and service-token modes remain **single operator** and are
not equivalent to end-user sign-in or per-user isolation.

This does **not** implement OIDC, browser sessions or production-ready
multi-user security. Review the scope, role policy and migration safety
notes in [docs/project-rbac-audit-foundation.md](docs/project-rbac-audit-foundation.md).

## OIDC resource-server verification (API-only preview)

A new optional `EVIDENCEOS_SECURITY_MODE=oidc` allows FastAPI to validate
RS256 JWT access tokens from a configured HTTPS issuer/JWKS endpoint, check
audience and expiry, and use the verified subject for project-scoped RBAC.
It does **not** implement user login, browser sessions, PKCE or logout.

For safety, the Next.js web application explicitly **returns 503** in this
mode until a maintained OAuth2/OIDC browser login and session workflow is
implemented. Continue using the existing localhost modes for the current UI.
Never expose the prototype as a public multi-user production service.
See [OIDC resource-server guide](docs/oidc-resource-server.md).
