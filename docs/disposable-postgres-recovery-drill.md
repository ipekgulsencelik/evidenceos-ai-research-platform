# PostgreSQL encrypted backup / isolated restore drill

**Scope:** CI-only synthetic disaster-recovery validation. This is NOT a
production backup policy, a production data backup, or an actual production
RPO/RTO exercise. Reference: [Issue #38](https://github.com/ipekgulsencelik/evidenceos-ai-research-platform/issues/38).

## What the automatic drill does

1. Requires `GITHUB_ACTIONS=true` **and** the explicit environment opt-in
   `EVIDENCEOS_DRILL_CONFIRM=isolated-synthetic-only`. Refuses to start if
   `EVIDENCEOS_DATABASE_URL`, `DATABASE_URL`, `PGHOST` or `PGDATABASE`
   is present. Never accepts an external DSN or caller-specified database name.
2. Builds on the existing **CI-only** `evidenceos-api:ci` image. Creates
   two uniquely named PostgreSQL 16 containers with fresh random CI-only
   credentials on a new **internal** Docker bridge network. **No host ports,
   bind mounts or persistent Docker volumes** are used.
3. Runs the repository's actual Alembic migrations in the **source** instance
   and inserts fixed synthetic projects, owner/viewer memberships and
   allow/deny audit events (two records per table).
4. Streams `pg_dump -Fc --no-owner --no-acl` into a **symmetric,
   integrity-protected GnuPG OpenPGP AES-256 encrypted file**, with a
   newly generated ephemeral passphrase. The encrypted archive is kept
   only in a private temporary CI directory.
5. Corrupts a separate copy of the archive and verifies that decrypting it
   fails. Decrypts the original to a temporary **synthetic plaintext**
   custom-format archive, then restores into a **different empty target
   instance** using `pg_restore --exit-on-error --no-owner --no-acl`.
6. Validates project/membership/audit counts and content fingerprints,
   verifies restored Alembic revision, and confirms the source database
   remains unchanged. Emits only status and illustrative timings.
7. On success or failure, removes both throwaway containers, their network
   and the private temporary directory.

All generated credentials, archive bytes, SQL rows and passphrases stay
out of CI artifacts, GitHub commits and successful job output. The
temporary decrypted file contains **only synthetic fixtures** and is never
designed for real/regulated datasets. There are no commands targeting
`compose.yaml`, `compose.oidc-staging.yaml` or an existing deployment.
A green CI step demonstrates **only this isolated recovery exercise**.

## CI execution

The `docker` GitHub Actions job builds `evidenceos-api:ci`, then executes:

```bash
bash -n scripts/drill_disposable_postgres_backup.sh
GITHUB_ACTIONS=true EVIDENCEOS_DRILL_CONFIRM=isolated-synthetic-only \
  bash scripts/drill_disposable_postgres_backup.sh
```

This requires a Linux runner with Docker, OpenSSL, Python 3 and GnuPG.
The GitHub runner supplies `GITHUB_ACTIONS=true` automatically.
Do not copy the command into a real server or set that variable to bypass
the intended CI-only safety boundary.

On success, the report includes:

```text
DISPOSABLE_RECOVERY_DRILL_PASS projects=2 memberships=2 audit_events=2
Encrypted_archive=OpenPGP_AES256 tamper_rejected=true source_unchanged=true
Sample_restore_seconds=<number> sample_snapshot_age_seconds=<number>
```

The numerical values are demonstration measurements on GitHub's disposable
runner, not SLOs. **Sample snapshot age does not establish an RPO.** RPO
requires a production backup schedule, max data loss target and restore
validation under realistic incident conditions; RTO requires end-to-end
incident-recovery duration, including operations and upstream dependencies.

## Remaining production requirements

- Deploy a **separate, least-privilege backup identity** and managed
  secrets; do not pass real credentials into Docker inspectable environment
  variables or GitHub Actions plaintext settings.
- Select verified off-host encrypted storage with object versioning or
  immutability, a retention/deletion policy, service account boundaries,
  encryption key rotation, independent key recovery, and real backup
  freshness monitoring. OpenPGP encryption here is a proof of mechanism,
  not an approved key-management system.
- Design physical snapshots/WAL/PITR for continuous point-in-time recovery,
  if the application's RPO requires it. A logical nightly `pg_dump`
  cannot provide low data-loss RPO by itself.
- Exercise a **production-like, entirely separate** restore into a
  dedicated non-production environment using realistic schema size,
  permissions, migration history and service startup checks.
- Validate checksum and record consistency beyond three synthetic tables,
  external object storage, project isolation/RBAC and dependent service
  state (including session Redis and the IdP).
- Publish an incident recovery/rollback runbook, backup owner/escalation,
  alert thresholds and objective RPO/RTO targets before pilot approval.

This feature implements the **synthetic CI drill milestone**, not every
acceptance criterion of Issue #38. Leave Issue #38 open until those
operational requirements are demonstrated and approved.
