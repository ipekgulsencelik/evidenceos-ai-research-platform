"""Offline-only backup policy contract checks; never connects to a database.

The validator checks declared configuration consistency, NOT operational
proof that the described cloud resources or backups exist.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED: dict[str, set[str]] = {
    "recovery": {
        "backup_mode",
        "target_rpo_minutes",
        "target_rto_minutes",
        "backup_interval_minutes",
        "wal_archive_max_gap_minutes",
    },
    "storage": {
        "offsite",
        "private_access",
        "encrypted_at_rest",
        "tls_in_transit",
        "immutable",
        "separate_failure_domain",
        "retention_days",
    },
    "key_management": {
        "managed_kms",
        "separate_restore_principal",
        "key_rotation_runbook",
        "break_glass_key_recovery",
    },
    "alerts": {
        "backup_failed",
        "backup_stale",
        "restore_drill_failed",
        "wal_archive_gap",
    },
    "rehearsal": {
        "isolated_target",
        "restore_interval_days",
        "schema_version_verified",
        "rbac_audit_verified",
        "application_smoke_test",
    },
    "ownership": {"backup_operator", "recovery_approver", "incident_lead"},
}
TOP_LEVEL = {"schema_version", "environment", "postgres_major", *REQUIRED}
REQUIRED_TRUE = {
    "storage": {
        "offsite",
        "private_access",
        "encrypted_at_rest",
        "tls_in_transit",
        "immutable",
        "separate_failure_domain",
    },
    "key_management": {
        "managed_kms",
        "separate_restore_principal",
        "key_rotation_runbook",
        "break_glass_key_recovery",
    },
    "alerts": {"backup_failed", "backup_stale", "restore_drill_failed"},
    "rehearsal": {
        "isolated_target",
        "schema_version_verified",
        "rbac_audit_verified",
        "application_smoke_test",
    },
}
BACKUP_MODES = {"physical_wal", "managed_snapshot_wal", "logical_only"}
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,63}$")
PLACEHOLDER_PREFIXES = ("TBD", "TODO", "REQUIRED", "SET_", "UNASSIGNED", "CHOOSE")


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _check_keys(value: object, needed: set[str], where: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{where}: must be an object")
        return {}
    actual = set(value)
    for key in sorted(needed - actual):
        errors.append(f"{where}.{key}: missing")
    for key in sorted(actual - needed):
        errors.append(f"{where}.{key}: unexpected field (credentials are prohibited)")
    return value


def validate_policy(value: object) -> list[str]:
    """Return field-path errors only: user-supplied values are never printed."""
    errors: list[str] = []
    policy = _check_keys(value, TOP_LEVEL, "policy", errors)
    if policy.get("schema_version") != 1 or type(policy.get("schema_version")) is not int:
        errors.append("policy.schema_version: expected 1")
    if policy.get("environment") not in ("staging", "production"):
        errors.append("policy.environment: choose staging or production")
    if type(policy.get("postgres_major")) is not int or policy.get("postgres_major") != 16:
        errors.append("policy.postgres_major: must match PostgreSQL 16 deployment baseline")

    sections = {
        name: _check_keys(policy.get(name), fields, f"policy.{name}", errors)
        for name, fields in REQUIRED.items()
    }

    for section, fields in REQUIRED_TRUE.items():
        for key in fields:
            if sections[section].get(key) is not True:
                errors.append(f"policy.{section}.{key}: must be explicitly true")

    recovery = sections["recovery"]
    mode = recovery.get("backup_mode")
    if not isinstance(mode, str) or mode not in BACKUP_MODES:
        errors.append("policy.recovery.backup_mode: unsupported")
    number_fields = {
        "recovery": ("target_rpo_minutes", "target_rto_minutes", "backup_interval_minutes"),
        "storage": ("retention_days",),
        "rehearsal": ("restore_interval_days",),
    }
    for section, fields in number_fields.items():
        for key in fields:
            if not _positive_int(sections[section].get(key)):
                errors.append(f"policy.{section}.{key}: positive integer required")
    gap = recovery.get("wal_archive_max_gap_minutes")
    if mode in ("physical_wal", "managed_snapshot_wal"):
        if not _positive_int(gap):
            errors.append("policy.recovery.wal_archive_max_gap_minutes: required for WAL")
        elif _positive_int(recovery.get("target_rpo_minutes")) and gap > recovery["target_rpo_minutes"]:
            errors.append("policy.recovery.wal_archive_max_gap_minutes: exceeds target RPO")
        if sections["alerts"].get("wal_archive_gap") is not True:
            errors.append("policy.alerts.wal_archive_gap: required for WAL")
    elif mode == "logical_only":
        if gap is not None:
            errors.append("policy.recovery.wal_archive_max_gap_minutes: must be null for logical-only")
        if (
            _positive_int(recovery.get("backup_interval_minutes"))
            and _positive_int(recovery.get("target_rpo_minutes"))
            and recovery["backup_interval_minutes"] > recovery["target_rpo_minutes"]
        ):
            errors.append("policy.recovery.backup_interval_minutes: exceeds target RPO")
        if sections["alerts"].get("wal_archive_gap") is not False:
            errors.append("policy.alerts.wal_archive_gap: must be false for logical-only")

    for role, name in sections["ownership"].items():
        if (
            not isinstance(name, str)
            or IDENTIFIER.fullmatch(name) is None
            or name.upper().startswith(PLACEHOLDER_PREFIXES)
        ):
            errors.append(f"policy.ownership.{role}: assign a team/role identifier")

    return sorted(set(errors))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/backup_policy_contract.py <policy.json>", file=sys.stderr)
        return 2
    try:
        policy = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("Could not read a valid JSON policy file.", file=sys.stderr)
        return 2
    errors = validate_policy(policy)
    if errors:
        print("Backup policy contract is incomplete:", file=sys.stderr)
        for problem in errors:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("Backup policy contract is structurally valid.")
    print("This does NOT prove backup availability, restore success, or production readiness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
