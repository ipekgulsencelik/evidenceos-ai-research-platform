# EvidenceOS — Phase 1 Project Foundation

[![CI](https://img.shields.io/badge/CI-configured-blue)](#quality-gates)

An evidence-first platform for academic and legal research. **This repository is
an infrastructure and domain foundation, not yet a functioning research/LLM
product.** Academic connectors, legal retrieval, claim verification and the
Next.js UI are upcoming phases.

## Stack

Python 3.12, uv, FastAPI, Pydantic Settings, SQLAlchemy 2 async, PostgreSQL 16,
Alembic, Pytest, Ruff, mypy, Docker Compose, GitHub Actions.

## Quick start (Windows PowerShell / macOS / Linux)

Requirements: Docker Desktop or Docker Engine with Compose.

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

The Docker API is exposed only on **127.0.0.1:8001** by default. The container still listens on port 8000. Set `EVIDENCEOS_API_HOST_PORT` in the root `.env` if 8001 is occupied. PostgreSQL is internal to the Docker network. Test via:

```bash
curl http://localhost:8001/api/v1/health/live
curl http://localhost:8001/api/v1/health/ready
```

On PowerShell, use `Invoke-RestMethod` or `curl.exe`. For example:

```powershell
Invoke-RestMethod http://localhost:8001/api/v1/health/live
Invoke-RestMethod -Method Post http://localhost:8001/api/v1/projects `
  -ContentType 'application/json' `
  -Body '{"title":"AI in adolescents","domain":"academic"}'
```

For development only, OpenAPI interactive docs: http://localhost:8001/docs

Stop and clean:

```bash
docker compose down        # preserves DB volume
docker compose down -v     # deletes all local database data!
```

**Security:** The example uses local-only credentials. Change the password,
never commit `.env`, and **do not expose to the Internet**: authentication,
authorization, rate limiting, secure ingress and tenant isolation are not part
of this first commit. URL-encode any special characters in a database password.

### Windows quick setup

From PowerShell in the repository root:

```powershell
.\scripts\first-run.ps1
```

With Python/uv available, the local quality commands are packaged in
`.\scripts\check.ps1` (requires dependency downloads at least once).

## Development with uv

```bash
cd apps/api
uv python install 3.12
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q --cov=evidenceos --cov-report=term-missing
```

To run API locally alongside just PostgreSQL in Docker:

```bash
# from repository root
cp .env.example .env
docker compose up -d db
cd apps/api
# configure EVIDENCEOS_DATABASE_URL using a local env, or set in shell
uv run alembic upgrade head
uv run uvicorn evidenceos.presentation.api.app:app --reload
```

Environment variables are read from the **working directory** (`apps/api` when
using `uv run`), so either export `EVIDENCEOS_DATABASE_URL` there or create a
private `apps/api/.env` with the same settings. Both `.env` locations are ignored
by Git. A database migration is required before creating projects.

## API endpoints

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/health/live` | Process liveness; no DB round trip |
| GET | `/api/v1/health/ready` | DB readiness (`SELECT 1`) |
| POST | `/api/v1/projects` | Create academic/legal research project |
| GET | `/api/v1/projects/{id}` | Retrieve a project by UUID |

Example:

```bash
curl -X POST http://localhost:8001/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"title":"Legal research","domain":"legal"}'
```

## Quality gates

CI runs lint, formatting, strict mypy, unit/API/in-memory adapter tests with
coverage, an actual PostgreSQL migration+integration test, and Docker build.
The optional PostgreSQL test runs automatically in CI, but skips without an
explicit `EVIDENCEOS_TEST_DATABASE_URL`. Use a disposable test database only;
never point it at production data.

```bash
cd apps/api
uv run pytest -q
```

`uv.lock` is checked in. `uv sync` prevents drift between the declared
dependencies and the lockfile (see https://docs.astral.sh/uv/concepts/projects/sync/).

## Architecture

```text
apps/api/src/evidenceos/
  domain/              # pure entities, business rules and UoW/repository ports
  application/         # use cases, no framework or storage coupling
  infrastructure/      # PostgreSQL persistence and validated configuration
  presentation/api/    # FastAPI composition, dependency wiring, HTTP schemas
```

See [`docs/architecture`](docs/architecture/README.md) and
[`docs/adr`](docs/adr/0001-modular-monolith.md).

## Roadmap

1. **Included in foundation:** research project aggregate, transactional
   repository adapter, migrations, health/ready endpoints, typed configuration,
   Docker setup, CI, tests, documentation.
2. **Next:** OpenAlex search adapter and Crossref metadata verification with
   provenance and API contract tests.
3. **Then:** permissioned PDF parsing, evidence extraction and claim checking.
4. **Later:** legal sources, time-aware laws and judgment verification,
   identity/RBAC, multi-tenant security and production hardening.

## Scope and reliability

No claims of production readiness are made for this repository; it is
**production-oriented scaffolding** and requires threat modeling, secure
identity, load testing, observability, and operational review before deployment.


## Phase 1.1 — Academic Research Engine

EvidenceOS now has provider-neutral academic metadata workflows:

- `GET /api/v1/academic/works?query=artificial%20intelligence&limit=10` searches OpenAlex.
- `POST /api/v1/academic/citations/verify` with JSON
  `{"doi":"10.1000/xyz","expected_title":"Article title"}` retrieves Crossref metadata.
- Citation statuses: `verified`, `title_mismatch`, `not_found_in_crossref`.
  **Verified only means the DOI metadata exists and an optional title matches**;
  it does *not* mean an article supports an argument or that a DOI is valid across
  all registration agencies when Crossref does not have it.
- `502` indicates an upstream failure; `503` is returned when the OpenAlex key
  is not configured. Errors are never silently reported as empty results.

### Configuration

Get an OpenAlex API key from https://openalex.org/settings/api and set
`EVIDENCEOS_OPENALEX_API_KEY` in your local `.env`. This key is never checked in.
Set `EVIDENCEOS_CROSSREF_CONTACT_EMAIL` to identify your project for Crossref's
polite API pool. Both providers are called via HTTPS and are covered by offline
mock-transport tests. The search feature requires an active Internet connection.

### Architectural boundary

`domain/ports/academic.py` defines academic search and citation metadata
interfaces. Use cases depend only on these ports. OpenAlex and Crossref adapters
live in `infrastructure/providers`; FastAPI dependency functions are the
composition root. Legal research and full-text claim verification are not yet
implemented. Authentication, rate limiting, and audit logging are required
before exposing a public deployment.
