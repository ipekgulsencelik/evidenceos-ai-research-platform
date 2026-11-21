FROM ghcr.io/astral-sh/uv:0.10.0 AS uv-bin
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv-bin /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN uv sync --no-dev --no-editable && \
    useradd --uid 10001 --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "evidenceos.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
