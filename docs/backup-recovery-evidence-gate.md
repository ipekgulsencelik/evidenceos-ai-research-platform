# Backup recovery evidence health gate (offline foundation)

**Status: a fail-closed evidence consistency check, NOT a deployed backup
monitor, scheduled job, trusted storage client, KMS integration or proof
that production can recover.** EvidenceOS production remains blocked.

The existing [policy validator](../scripts/backup_policy_contract.py)
checks the declarations (targets, owners, planned controls); this gate
checks **separately provided observations** about a backup, WAL archives
and an isolated restore rehearsal. Those observations must eventually
come from a **trusted, independently authenticated backup catalog and
restore scheduler**, not a user-edited JSON file. This repository does
not currently supply that provider adapter or attestation.

## Input contract

The caller supplies two UTF-8 JSON documents of at most 32 KiB each:

- A **completed, separately reviewed policy**, following
  `deploy/backup/recovery-policy.example.json`. The committed example is
  intentionally incomplete and cannot pass.
- A backup/restore **observation**, following
  `deploy/backup/recovery-evidence.example.json`. This example
  intentionally contains unset times and `false` verification flags;
  it **must not** pass.

Only exact schema keys are accepted. The evidence includes:

- `observed_at`: timestamp for the independently collected observation,
  in UTC `YYYY-MM-DDTHH:MM:SSZ` format.
- `backup.snapshot_at`: actual recovery-consistent snapshot point,
  **not** the end of the backup transfer.
- `backup.completed_at` and `backup.offsite_verified_at`: completion
  and independently confirmed offsite verification time.
- Backup encryption, immutability and integrity verification flags.
- `wal.last_contiguous_at` and verified continuity for WAL/PITR policy
  modes. Logical-only mode requires `wal: null`.
- `restore.started_at`, `restore.completed_at`, isolated destination,
  data integrity, schema, RBAC, access audit and application-smoke
  verification claims.

No database names, project identifiers, regions, network endpoints,
credentials, JWTs, query text or archived research content are required
or permitted as additional keys. Unknown keys are rejected without
printing their names or values; duplicate JSON fields are also rejected.

## Evaluation / failure behavior

The policy must pass the previous validator, and the observation's
environment must match. This evaluator rejects:

1. Missing/malformed fields, UTC timestamps, invalid ordering, future
   observation timestamps, or observations older than **5 minutes**.
2. Missing encryption, immutable offsite copy or integrity verification.
3. Backups older than the declared backup cadence.
4. A latest stated recoverable point older than the **declared RPO**.
   For WAL/PITR policy, this point is the last **contiguous** archived
   WAL timestamp with continuity verified. For logical-only policy it
   is the database snapshot point, **not** the time the export finished.
5. WAL archive gaps beyond the policy threshold.
6. A restore rehearsal older than the approved rehearsal interval,
   missing isolation, schema/RBAC/audit/app verification, or with a
   rehearsal duration above the declared RTO *planning threshold*.

A backup can pass the cadence check yet fail the WAL freshness check;
both are evaluated separately. A failed verification raises a static
error code and process exit code 1. Unreadable/oversized/duplicate-key
JSON exits 2. Success exits 0, but means **only the supplied declarations
are internally consistent**. The CLI never logs raw JSON or file content.

The duration of a synthetic or restricted restore rehearsal is NOT a
measured *production incident RTO*. Real recovery includes detection,
authorization, data service restoration, Redis/IdP coordination and
cutover. Equally, a self-reported WAL timestamp does NOT establish
that all segments actually exist or have been restored.

## Run safely

No network access is performed by this script:

```powershell
python scripts/backup_recovery_evidence.py path/to/private/policy.json path/to/private/observation.json
```

The committed examples are **expected to fail**. To run entirely
synthetic tests (no Postgres or Docker required):

```powershell
python -m unittest discover -s scripts -p "test_backup_recovery_evidence.py" -v
```

The PR CI runs those tests and deliberately asserts that invalid
templates fail. Do not add actual backup credentials or infrastructure
identifiers to JSON, CI logs or GitHub issues.

## Remaining production infrastructure

The next implementation requires selecting a hosting provider, backup
service, object storage, key manager and an approved RPO/RTO. Build a
least-privilege catalog reader/monitor that authenticates to that
provider, checks immutable offsite backup status and actual WAL
continuity, records signed/traceable evidence, and sends actionable
alerts into a managed operations channel. Prove a separate-target
restore at representative size, and verify source-of-truth provenance
rather than trusting handwritten success flags.

**No production backup schedule, KMS, offsite repository, privileged
restore role, automated real-world alarm, or incident cutover is
provisioned by this milestone.** Keep [Issue #38](https://github.com/ipekgulsencelik/evidenceos-ai-research-platform/issues/38)
open until those independent operational gates are met.
