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

Development dependencies are declared in `package.json`; a checked-in npm lockfile is still a hardening task. Do not claim reproducible dependency resolution until `package-lock.json` is committed.
