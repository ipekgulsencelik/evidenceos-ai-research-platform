# EvidenceOS foundation — local verification

Verification performed on 2026-11-21 in an offline Python 3.13 environment.

## Passed

- `PYTHONPATH=src:. pytest -q --cov=evidenceos --cov-report=term-missing --cov-fail-under=80`
- **18 passed, 2 skipped**; branch-inclusive coverage **83.95%**.
- Python syntax compilation: `python -m compileall -q src migrations tests`
- Parsed `pyproject.toml`, `compose.yaml` and `.github/workflows/ci.yml`.
- Architectural dependency test confirms inner layers do not import outer layers.

## Not run / deferred

- Docker image and real PostgreSQL: Docker service is not installed in this execution environment.
- Ruff and mypy: packages are not installed locally and registry access is unavailable. Their commands are configured in CI.
- SQLite/aiosqlite integration test: aiosqlite is not available; the test runs when `uv sync` installs dev dependencies.
- PostgreSQL integration test: requires an explicit disposable `EVIDENCEOS_TEST_DATABASE_URL`; configured in GitHub Actions.
- `uv.lock`: could not be generated because the package registry is unreachable; run `cd apps/api && uv lock` on a connected machine and commit the result. Before the lock is committed, `uv sync` is intentionally not run with `--locked`.

## Explicit production gaps

This is a production-oriented foundation, not a production-ready public service.
Authentication, authorization, request rate limiting, tenant isolation, source connectors,
trace collection, threat modeling, load testing, and advanced data governance have not yet
been implemented. Do not expose the API to the Internet or use sensitive real-user data.