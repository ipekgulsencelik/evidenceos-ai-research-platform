"""Read-only, fail-closed evaluation of backup and restore *claims*.

The evidence document must come from a separately authenticated backup
catalog or monitoring system. This tool NEVER connects to those systems.
Passing checks proves internal consistency only, not actual recoverability.
No URL, token, file content, arbitrary key or identifier enters output.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backup_policy_contract import validate_policy

OBSERVATION_MAX_AGE = timedelta(minutes=5)
MAX_INPUT_BYTES = 32 * 1024
_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

_TOP_KEYS = {"schema_version", "environment", "observed_at", "backup", "wal", "restore"}
_BACKUP_KEYS = {
    "snapshot_at",
    "completed_at",
    "offsite_verified_at",
    "encryption_verified",
    "immutability_verified",
    "integrity_verified",
}
_RESTORE_KEYS = {
    "started_at",
    "completed_at",
    "separate_target_verified",
    "integrity_verified",
    "schema_verified",
    "rbac_verified",
    "audit_verified",
    "application_smoke_verified",
}
_WAL_KEYS = {"last_contiguous_at", "continuity_verified"}
_BACKUP_TRUE = {"encryption_verified", "immutability_verified", "integrity_verified"}
_RESTORE_TRUE = {
    "separate_target_verified",
    "integrity_verified",
    "schema_verified",
    "rbac_verified",
    "audit_verified",
    "application_smoke_verified",
}


def _object(value: object, expected: set[str], field: str, problems: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        problems.append(f"{field}.not_object")
        return {}
    missing = expected - set(value)
    if missing:
        problems.append(f"{field}.missing_fields")
    if set(value) - expected:
        # Do not echo unknown keys. They could themselves contain secrets.
        problems.append(f"{field}.unknown_fields")
    return value


def _timestamp(value: object, field: str, problems: list[str]) -> datetime | None:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        problems.append(f"{field}.invalid_timestamp")
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        problems.append(f"{field}.invalid_timestamp")
        return None


def _ordered(
    earlier: datetime | None,
    later: datetime | None,
    field: str,
    problems: list[str],
) -> None:
    if earlier is not None and later is not None and earlier > later:
        problems.append(f"{field}.time_order")


def evaluate_evidence(
    policy_value: object, evidence_value: object, *, now: datetime
) -> list[str]:
    """Evaluate a provider-reported snapshot, WAL and rehearsal claim.

    Pure function; fails closed for malformed input. Returned errors are
    static codes only. `now` must be a UTC-aware reference supplied by the
    calling monitor, not trusted from the evidence document.
    """
    problems: list[str] = []
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        return ["clock.not_utc"]
    policy_errors = validate_policy(policy_value)
    if policy_errors:
        # Never print policy values or unknown input keys.
        return ["policy.invalid"]
    assert isinstance(policy_value, dict)
    policy = policy_value

    evidence = _object(evidence_value, _TOP_KEYS, "evidence", problems)
    if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != 1:
        problems.append("evidence.schema_version")
    if evidence.get("environment") != policy["environment"]:
        problems.append("evidence.environment_mismatch")

    observed = _timestamp(evidence.get("observed_at"), "evidence.observed_at", problems)
    backup = _object(evidence.get("backup"), _BACKUP_KEYS, "backup", problems)
    restore = _object(evidence.get("restore"), _RESTORE_KEYS, "restore", problems)
    for key in _BACKUP_TRUE:
        if backup.get(key) is not True:
            problems.append(f"backup.{key}.unverified")
    for key in _RESTORE_TRUE:
        if restore.get(key) is not True:
            problems.append(f"restore.{key}.unverified")

    snapshot_at = _timestamp(backup.get("snapshot_at"), "backup.snapshot_at", problems)
    completed_at = _timestamp(backup.get("completed_at"), "backup.completed_at", problems)
    offsite_at = _timestamp(backup.get("offsite_verified_at"), "backup.offsite_verified_at", problems)
    restore_started = _timestamp(restore.get("started_at"), "restore.started_at", problems)
    restore_completed = _timestamp(restore.get("completed_at"), "restore.completed_at", problems)

    _ordered(snapshot_at, completed_at, "backup", problems)
    _ordered(completed_at, offsite_at, "backup.offsite", problems)
    _ordered(offsite_at, observed, "backup.observation", problems)
    _ordered(restore_started, restore_completed, "restore", problems)
    _ordered(restore_completed, observed, "restore.observation", problems)

    if observed is not None:
        if observed > now:
            problems.append("evidence.future_observation")
        elif now - observed > OBSERVATION_MAX_AGE:
            problems.append("evidence.stale_observation")

    recovery: dict[str, Any] = policy["recovery"]
    rehearsal: dict[str, Any] = policy["rehearsal"]
    mode = recovery["backup_mode"]
    wal = evidence.get("wal")
    recoverable_at = snapshot_at

    if mode in {"physical_wal", "managed_snapshot_wal"}:
        record = _object(wal, _WAL_KEYS, "wal", problems)
        if record.get("continuity_verified") is not True:
            problems.append("wal.continuity_unverified")
        wal_at = _timestamp(record.get("last_contiguous_at"), "wal.last_contiguous_at", problems)
        _ordered(snapshot_at, wal_at, "wal.snapshot", problems)
        _ordered(wal_at, observed, "wal.observation", problems)
        recoverable_at = wal_at
        if wal_at is not None and now >= wal_at:
            age_minutes = (now - wal_at).total_seconds() / 60
            if age_minutes > recovery["wal_archive_max_gap_minutes"]:
                problems.append("wal.archive_gap_exceeded")
    elif wal is not None:
        problems.append("wal.must_be_null_for_logical")

    if completed_at is not None and now >= completed_at:
        backup_age = (now - completed_at).total_seconds() / 60
        if backup_age > recovery["backup_interval_minutes"]:
            problems.append("backup.interval_exceeded")
    if recoverable_at is not None:
        if recoverable_at > now:
            problems.append("recovery.point_in_future")
        elif (now - recoverable_at).total_seconds() / 60 > recovery["target_rpo_minutes"]:
            problems.append("recovery.recoverable_point_too_old")

    if restore_completed is not None:
        if restore_completed > now:
            problems.append("restore.completed_in_future")
        elif now - restore_completed > timedelta(days=rehearsal["restore_interval_days"]):
            problems.append("restore.rehearsal_stale")
    if restore_started is not None and restore_completed is not None:
        if restore_started <= restore_completed and (
            restore_completed - restore_started
        ).total_seconds() / 60 > recovery["target_rto_minutes"]:
            # This is ONLY a rehearsal-duration planning gate; it does not
            # establish end-to-end production incident RTO.
            problems.append("restore.sample_duration_over_target")

    return sorted(set(problems))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _load_json(path: str) -> object:
    candidate = Path(path)
    if candidate.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("JSON input exceeds safe size")
    return json.loads(candidate.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python scripts/backup_recovery_evidence.py <policy.json> <evidence.json>",
            file=sys.stderr,
        )
        return 2
    try:
        policy = _load_json(sys.argv[1])
        evidence = _load_json(sys.argv[2])
    except (OSError, ValueError, UnicodeError):
        print("Unable to load valid small JSON policy/evidence files.", file=sys.stderr)
        return 2
    problems = evaluate_evidence(policy, evidence, now=datetime.now(timezone.utc))
    if problems:
        print("BACKUP_EVIDENCE_INCONSISTENT", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("BACKUP_EVIDENCE_DECLARATIONS_CONSISTENT")
    print("Not proof of deployed backups, authenticated evidence or production recovery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
