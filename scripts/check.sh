#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../apps/api"
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=evidenceos --cov-report=term-missing --cov-fail-under=80
