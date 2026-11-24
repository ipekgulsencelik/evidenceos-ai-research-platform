"""Offline backup policy validation tests; no database, cloud or network calls."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from backup_policy_contract import validate_policy


ROOT = Path(__file__).resolve().parent.parent


def valid_synthetic_policy() -> dict[str, object]:
    """Values are ONLY test fixtures, not recommended production objectives."""
    return {
        "schema_version": 1,
        "environment": "staging",
        "postgres_major": 16,
        "recovery": {
            "backup_mode": "physical_wal",
            "target_rpo_minutes": 60,
            "target_rto_minutes": 240,
            "backup_interval_minutes": 1440,
            "wal_archive_max_gap_minutes": 10,
        },
        "storage": {
            "offsite": True,
            "private_access": True,
            "encrypted_at_rest": True,
            "tls_in_transit": True,
            "immutable": True,
            "separate_failure_domain": True,
            "retention_days": 30,
        },
        "key_management": {
            "managed_kms": True,
            "separate_restore_principal": True,
            "key_rotation_runbook": True,
            "break_glass_key_recovery": True,
        },
        "alerts": {
            "backup_failed": True,
            "backup_stale": True,
            "restore_drill_failed": True,
            "wal_archive_gap": True,
        },
        "rehearsal": {
            "isolated_target": True,
            "restore_interval_days": 14,
            "schema_version_verified": True,
            "rbac_audit_verified": True,
            "application_smoke_test": True,
        },
        "ownership": {
            "backup_operator": "platform-oncall",
            "recovery_approver": "security-reviewers",
            "incident_lead": "incident-commander",
        },
    }


class BackupPolicyContractTests(unittest.TestCase):
    def test_synthetic_complete_policy_passes(self) -> None:
        self.assertEqual(validate_policy(valid_synthetic_policy()), [])

    def test_published_template_must_not_be_accepted(self) -> None:
        template = json.loads(
            (ROOT / "deploy" / "backup" / "recovery-policy.example.json").read_text(
                encoding="utf-8"
            )
        )
        errors = validate_policy(template)
        self.assertTrue(errors)
        self.assertTrue(any("target_rpo_minutes" in item for item in errors))
        self.assertTrue(any("backup_operator" in item for item in errors))
        self.assertTrue(any("_warning" in item for item in errors))

    def test_rejects_missing_encryption_or_separate_approval(self) -> None:
        policy = valid_synthetic_policy()
        policy["storage"]["encrypted_at_rest"] = False  # type: ignore[index]
        policy["storage"]["immutable"] = False  # type: ignore[index]
        policy["key_management"]["separate_restore_principal"] = False  # type: ignore[index]
        errors = validate_policy(policy)
        self.assertTrue(any("encrypted_at_rest" in item for item in errors))
        self.assertTrue(any("immutable" in item for item in errors))
        self.assertTrue(any("separate_restore_principal" in item for item in errors))

    def test_rejects_wal_gap_exceeding_rpo_and_missing_alert(self) -> None:
        policy = valid_synthetic_policy()
        policy["recovery"]["wal_archive_max_gap_minutes"] = 90  # type: ignore[index]
        policy["alerts"]["wal_archive_gap"] = False  # type: ignore[index]
        errors = validate_policy(policy)
        self.assertTrue(any("wal_archive_max_gap_minutes" in item for item in errors))
        self.assertTrue(any("wal_archive_gap" in item for item in errors))

    def test_logical_backup_interval_cannot_exceed_target_rpo(self) -> None:
        policy = valid_synthetic_policy()
        policy["recovery"]["backup_mode"] = "logical_only"  # type: ignore[index]
        policy["recovery"]["backup_interval_minutes"] = 1440  # type: ignore[index]
        policy["recovery"]["wal_archive_max_gap_minutes"] = None  # type: ignore[index]
        policy["alerts"]["wal_archive_gap"] = False  # type: ignore[index]
        self.assertTrue(
            any("backup_interval_minutes" in item for item in validate_policy(policy))
        )
        policy["recovery"]["target_rpo_minutes"] = 2880  # type: ignore[index]
        self.assertEqual(validate_policy(policy), [])

    def test_no_credentials_or_unexpected_fields_are_allowed(self) -> None:
        policy = valid_synthetic_policy()
        policy["storage"]["backup_password"] = "SECRET-DO-NOT-ECHO"  # type: ignore[index]
        errors = validate_policy(policy)
        self.assertTrue(any("storage.backup_password" in item for item in errors))
        self.assertNotIn("SECRET-DO-NOT-ECHO", repr(errors))

    def test_invalid_types_are_fail_closed_without_crashing(self) -> None:
        policy = valid_synthetic_policy()
        policy["recovery"]["backup_mode"] = []  # type: ignore[index]
        policy["recovery"]["target_rpo_minutes"] = True  # type: ignore[index]
        policy["ownership"]["backup_operator"] = ["secret"]  # type: ignore[index]
        errors = validate_policy(policy)
        self.assertTrue(any("backup_mode" in item for item in errors))
        self.assertTrue(any("target_rpo_minutes" in item for item in errors))
        self.assertTrue(any("backup_operator" in item for item in errors))

    def test_missing_sections_are_rejected_without_crashing(self) -> None:
        policy = valid_synthetic_policy()
        del policy["storage"]
        self.assertTrue(any("policy.storage" in item for item in validate_policy(policy)))

    def test_input_not_modified(self) -> None:
        policy = valid_synthetic_policy()
        before = copy.deepcopy(policy)
        validate_policy(policy)
        self.assertEqual(policy, before)


if __name__ == "__main__":
    unittest.main()
