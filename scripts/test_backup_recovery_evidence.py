"""Deterministic, fully offline backup evidence evaluation regressions."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backup_policy_contract import validate_policy
from backup_recovery_evidence import _load_json, evaluate_evidence, main
from test_backup_policy_contract import valid_synthetic_policy

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def evidence() -> dict[str, object]:
    return {
        "schema_version": 1,
        "environment": "staging",
        "observed_at": "2026-01-01T12:00:00Z",
        "backup": {
            "snapshot_at": "2026-01-01T10:55:00Z",
            "completed_at": "2026-01-01T11:00:00Z",
            "offsite_verified_at": "2026-01-01T11:02:00Z",
            "encryption_verified": True,
            "immutability_verified": True,
            "integrity_verified": True,
        },
        "wal": {
            "last_contiguous_at": "2026-01-01T11:58:00Z",
            "continuity_verified": True,
        },
        "restore": {
            "started_at": "2026-01-01T11:30:00Z",
            "completed_at": "2026-01-01T11:36:00Z",
            "separate_target_verified": True,
            "integrity_verified": True,
            "schema_verified": True,
            "rbac_verified": True,
            "audit_verified": True,
            "application_smoke_verified": True,
        },
    }


def audit(value: object, *, now: datetime = NOW) -> list[str]:
    return evaluate_evidence(valid_synthetic_policy(), value, now=now)


class BackupEvidenceGateTests(unittest.TestCase):
    def test_fresh_verified_claims_are_internally_consistent(self) -> None:
        self.assertEqual(audit(evidence()), [])

    def test_missing_or_stale_observation_fails_closed(self) -> None:
        value = evidence()
        del value["observed_at"]
        self.assertIn("evidence.observed_at.invalid_timestamp", audit(value))
        self.assertIn("evidence.missing_fields", audit(value))
        self.assertIn(
            "evidence.stale_observation",
            audit(evidence(), now=NOW + timedelta(minutes=6)),
        )

    def test_future_or_ill_ordered_times_rejected(self) -> None:
        value = evidence()
        value["observed_at"] = "2026-01-01T12:02:00Z"
        self.assertIn("evidence.future_observation", audit(value))
        value = evidence()
        value["backup"]["offsite_verified_at"] = "2026-01-01T10:00:00Z"
        self.assertIn("backup.offsite.time_order", audit(value))

    def test_missing_backup_protections_cannot_pass(self) -> None:
        value = evidence()
        value["backup"]["immutability_verified"] = False
        value["backup"]["encryption_verified"] = False
        result = audit(value)
        self.assertIn("backup.immutability_verified.unverified", result)
        self.assertIn("backup.encryption_verified.unverified", result)

    def test_wal_archive_gap_and_recoverable_point_age(self) -> None:
        value = evidence()
        value["wal"]["last_contiguous_at"] = "2026-01-01T11:30:00Z"
        self.assertIn("wal.archive_gap_exceeded", audit(value))
        value["backup"]["snapshot_at"] = "2026-01-01T09:00:00Z"
        value["backup"]["completed_at"] = "2026-01-01T09:05:00Z"
        value["backup"]["offsite_verified_at"] = "2026-01-01T09:06:00Z"
        value["wal"]["last_contiguous_at"] = "2026-01-01T09:30:00Z"
        self.assertIn("recovery.recoverable_point_too_old", audit(value))

    def test_failed_or_stale_restore_and_long_sample(self) -> None:
        value = evidence()
        value["restore"]["audit_verified"] = False
        self.assertIn("restore.audit_verified.unverified", audit(value))
        value = evidence()
        value["restore"]["started_at"] = "2025-12-15T11:30:00Z"
        value["restore"]["completed_at"] = "2025-12-15T11:36:00Z"
        self.assertIn("restore.rehearsal_stale", audit(value))
        value = evidence()
        value["restore"]["started_at"] = "2025-12-31T07:30:00Z"
        self.assertIn("restore.sample_duration_over_target", audit(value))

    def test_logical_only_mode_has_no_wal_and_requires_fresh_snapshot(self) -> None:
        policy = valid_synthetic_policy()
        policy["recovery"]["backup_mode"] = "logical_only"
        policy["recovery"]["backup_interval_minutes"] = 30
        policy["recovery"]["wal_archive_max_gap_minutes"] = None
        policy["alerts"]["wal_archive_gap"] = False
        self.assertEqual(validate_policy(policy), [])
        value = evidence()
        value["wal"] = None
        value["backup"]["snapshot_at"] = "2026-01-01T11:45:00Z"
        value["backup"]["completed_at"] = "2026-01-01T11:50:00Z"
        value["backup"]["offsite_verified_at"] = "2026-01-01T11:52:00Z"
        self.assertEqual(evaluate_evidence(policy, value, now=NOW), [])
        value["backup"]["snapshot_at"] = "2026-01-01T10:00:00Z"
        self.assertIn(
            "recovery.recoverable_point_too_old",
            evaluate_evidence(policy, value, now=NOW),
        )
        value["wal"] = {"continuity_verified": True, "last_contiguous_at": "2026-01-01T12:00:00Z"}
        self.assertIn("wal.must_be_null_for_logical", evaluate_evidence(policy, value, now=NOW))

    def test_failed_policy_environment_and_unknown_keys(self) -> None:
        value = evidence()
        value["environment"] = "production"
        value["secret_token_123"] = "MUST_NOT_LEAK_THIS"
        result = audit(value)
        self.assertIn("evidence.environment_mismatch", result)
        self.assertIn("evidence.unknown_fields", result)
        self.assertNotIn("MUST_NOT_LEAK_THIS", json.dumps(result))
        policy = valid_synthetic_policy()
        policy["storage"]["immutable"] = False
        self.assertEqual(evaluate_evidence(policy, value, now=NOW), ["policy.invalid"])

    def test_invalid_nested_objects_and_timestamps_are_errors_not_crashes(self) -> None:
        value = evidence()
        value["wal"] = ["bad"]
        value["backup"] = None
        value["restore"] = {"started_at": "2026-18-99T10:00:00Z"}
        result = audit(value)
        self.assertIn("wal.not_object", result)
        self.assertIn("backup.not_object", result)
        self.assertIn("restore.completed_at.invalid_timestamp", result)
        self.assertIn("restore.started_at.invalid_timestamp", result)

    def test_input_unchanged(self) -> None:
        value = evidence()
        original = copy.deepcopy(value)
        self.assertEqual(audit(value), [])
        self.assertEqual(value, original)

    def test_duplicate_json_and_large_payload_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaises(ValueError):
                _load_json(str(path))
            path.write_text(" " * (33 * 1024), encoding="utf-8")
            with self.assertRaises(ValueError):
                _load_json(str(path))

    def test_cli_fails_closed_without_echoing_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "policy.json"
            declared = Path(directory) / "evidence.json"
            policy.write_text(json.dumps(valid_synthetic_policy()), encoding="utf-8")
            bad = evidence()
            bad["api_key"] = "ULTRA-SECRET-NEVER-LOG"
            declared.write_text(json.dumps(bad), encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["backup_recovery_evidence.py", str(policy), str(declared)]):
                with redirect_stderr(output):
                    result = main()
            self.assertEqual(result, 1)
            self.assertNotIn("ULTRA-SECRET", output.getvalue())


if __name__ == "__main__":
    unittest.main()
