"""Tests do not require a running database unless explicitly marked."""

import os

os.environ.setdefault("EVIDENCEOS_APP_ENV", "test")
os.environ.setdefault(
    "EVIDENCEOS_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)
