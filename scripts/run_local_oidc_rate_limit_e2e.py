"""Run a fresh-browser Keycloak + Redis rate-limit acceptance test locally.

This deliberately bypasses a user's possibly expired DevTools browser session.
It never prints staging usernames, passwords, session cookies, or bearer tokens.
The isolated API must first be started with the opt-in rate-limit overlay.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from run_local_oidc_e2e import ROOT, read_test_credentials

CONFIG = "playwright.rate-limit.config.mjs"


def main() -> int:
    try:
        credentials = read_test_credentials()
    except (OSError, ValueError) as exc:
        # Do not include file content or credentials in diagnostic messages.
        print(f"Local E2E environment is not ready: {type(exc).__name__}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.update(credentials)
    env["EVIDENCEOS_E2E_ALLOW_LOCAL_HTTP"] = "1"

    print("Running isolated Keycloak/Redis rate-limit acceptance with a fresh browser.")
    print("Only HTTP status codes and retry timing will be printed.")
    executable = "npx.cmd" if os.name == "nt" else "npx"
    try:
        result = subprocess.run(
            [executable, "--no-install", "playwright", "test", "--config", CONFIG],
            cwd=ROOT / "apps" / "web",
            env=env,
            check=False,
        )
    except FileNotFoundError:
        print("Install Node.js and Playwright locally in apps/web.", file=sys.stderr)
        return 1
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
