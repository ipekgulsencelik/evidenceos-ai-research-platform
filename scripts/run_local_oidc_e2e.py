"""Run the real-provider Playwright suite using untracked local test credentials.

No staging password or bearer token is ever printed by this launcher.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.oidc-staging"
EXPECTED_ORIGIN = "http://127.0.0.1:3101"
REQUIRED = (
    "EVIDENCEOS_E2E_ORIGIN",
    "EVIDENCEOS_E2E_USER_A",
    "EVIDENCEOS_E2E_PASSWORD_A",
    "EVIDENCEOS_E2E_USER_B",
    "EVIDENCEOS_E2E_PASSWORD_B",
)


def read_test_credentials() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if sep and name in REQUIRED:
            values[name] = value
    if any(not values.get(name) for name in REQUIRED):
        raise ValueError("Incomplete E2E test environment")
    if values["EVIDENCEOS_E2E_ORIGIN"] != EXPECTED_ORIGIN:
        raise ValueError("Refusing to run a local E2E test against a non-loopback origin")
    if values["EVIDENCEOS_E2E_USER_A"] == values["EVIDENCEOS_E2E_USER_B"]:
        raise ValueError("Two distinct staging identities are required")
    return values


def main() -> int:
    if not ENV_FILE.is_file():
        print("Prepare the isolated OIDC staging environment first.", file=sys.stderr)
        return 1
    try:
        credentials = read_test_credentials()
    except ValueError as exc:
        print(f"OIDC local E2E configuration error: {exc}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env.update(credentials)
    env["EVIDENCEOS_E2E_ALLOW_LOCAL_HTTP"] = "1"
    print(
        "Running genuine OIDC browser tests against disposable loopback staging. "
        "No credentials will be displayed by the launcher."
    )
    command = "npx.cmd" if os.name == "nt" else "npx"
    try:
        result = subprocess.run(
            [command, "playwright", "test", "--config", "playwright.staging.config.mjs"],
            cwd=ROOT / "apps" / "web",
            env=env,
            check=False,
        )
    except FileNotFoundError:
        print("Node.js and Playwright are required in apps/web.", file=sys.stderr)
        return 1
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
