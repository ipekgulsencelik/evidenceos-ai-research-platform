# Production backup architecture decision record (proposal)

**Status: proposed / not implemented / not approved.** This record proposes
a provider-independent control design for PostgreSQL backup and restore.
It does **not** provision backup schedules, cloud storage, keys, or access.
Do not point the synthetic CI drill at live databases.

## Decisions that must be made by owners

Before production or a sustained pilot, the business owner and security
reviewer must agree on a maximum tolerable data loss (RPO), end-to-end
service recovery time (RTO), legal/contractual retention and deletion
requirements, hosting platform, data residency and custodians. Numbers in
tests are **synthetic fixtures**, not proposed operational objectives.

| Decision | Required sign-off evidence |
| --- | --- |
| RPO, RTO, capacity | Target minutes, realistic database size, representative peak write rate, named approver |
| Recovery model | Managed snapshots **plus WAL** or audited physical base backups **plus WAL** for point-in-time recovery; logical dumps may supplement, not replace PITR where strict RPO is needed |
| Storage | Encrypted and access-controlled off-host immutable retention in a separate failure domain, with legal hold/deletion policy and recoverable account isolation |
| Keys | Managed key service, independent role authorized to decrypt during incident, rotation, break-glass and key-loss drills with dual control |
| Identities | Least-privilege backup writer, read-only verifier, separate restore operator and approver; never reuse app/DB superuser |
| Monitoring | Alerts for missed backups, staleness, WAL archival gaps, failed scheduled restore and approaching capacity/retention limits |
| Restore | New isolated instance, version-compatible tools/extension availability, schema/audit/RBAC integrity, application smoke checks, exact provenance of recovery point |
| Lifecycle | Restore test cadence, evidence retention, rollback and incident escalation, security review before pilot |

## Reference data flow

1. Postgres 16 produces managed/base snapshots and continuous WAL archives
   through a production-selected, vetted service. For supported logical
   exports, use `pg_dump` custom format as a *secondary* portability check.
2. Backups are sent over verified TLS into a different fault domain and
   encrypted with a key not controlled by the application runtime. Use a
   managed key service with audited grants and an independent recovery
   path. Merely enabling object-store encryption does **not** guarantee
   recoverability if the key is later lost or disabled.
3. Protect recovery points against accidental deletion and ransomware
   using immutable retention; define a distinct deletion principal and
   test retention-lock enforcement. Apply access logs to the backup store.
4. Automated verification checks *both* backup age and archive completeness;
   schedule restores into separate environments rather than attempting to
   validate backups by overwriting the primary.
5. Recovery operators verify the chosen snapshot/WAL time, restore to a
   **new** resource, run data integrity and application checks, then obtain
   explicit approval for cutover. The original database is retained for
   investigation and rollback until authorized disposal.

### Consistency across other EvidenceOS services

PostgreSQL is the durable research store; Redis participates in OIDC
session revocation and rate limits. A restored Postgres backup is **not**
a snapshot of identity-provider state or active Redis sessions. During
cutover, invalidate/recreate application sessions as appropriate, keep
unknown sessions rejected, and reverify OIDC issuer, signing keys, cookie
security and project-scoped RBAC. Do not force-open Redis or disable rate
limiting to make service appear healthy. Document dependencies on external
research providers separately.

## Failure-mode matrix

| Failure | Safe expected behavior | Operational evidence |
| --- | --- | --- |
| Missed backup / stale snapshot | Alert and hold pilot promotion; start incident investigation | Timestamped, independent backup age record |
| Missing WAL segment | Alert immediately; do not claim target RPO or PITR recovery point | Independent WAL sequence/gap verification |
| Storage compromised / deleted | Use protected immutable replica in another failure domain; revoke compromised credentials | Retention-lock test and security audit |
| KMS inaccessible | Fail closed; invoke tested independent recovery authorization, not plaintext fallback | Key recovery exercise and approvals |
| Archive corrupted | Reject restore; select verified prior recovery point and assess RPO breach | Integrity failure logged without contents |
| New target fails schema/integrity | No cutover, preserve original; investigate and redo from another point | Checksum counts + migration revision + RBAC/audit checks |
| Redis lost on restart | Reject unknown sessions and fail closed on protected rate-limited endpoints; rebuild protected Redis with new credentials | OIDC/rate-limit regressions |
| IdP unavailable | Deny new verification; do not disable auth to recover | IdP outage runbook and monitored 503s |
| Partial recovery and DNS cutover | Keep old resources isolated; cut over only after sign-off, with tested rollback path | Change record and rollback rehearsal |

## Machine-checkable *declaration* contract

This repository ships `deploy/backup/recovery-policy.example.json` as an
**intentionally invalid, non-deployable template**. It omits selected
objectives and owners, and includes a warning field that the validator
deliberately rejects.

After setting up a separate, privately managed policy document (not a
credential file), the operator can run **offline**:

```powershell
python scripts/backup_policy_contract.py path/to/private/recovery-policy.json
```

The validator checks required declarations, compatible restore mode,
positive targets, WAL-gap/RPO consistency, least-privilege assertions,
immutable storage, and named operational *roles* (not names, emails or
credentials). The file must not contain passwords, connection strings,
access tokens, private keys or research data. An unexpected field is
rejected. Do not commit a deployment-specific policy with sensitive
infrastructure identifiers or credentials.

**Important:** A valid declaration is not evidence that any cloud control,
immutable lock, key service, backup job, alert or restore process is
deployed or functioning. A reviewer must independently observe those
systems and attach private evidence to a change/release record.

## Release readiness evidence

- Approved RPO/RTO and capacity sizing with named accountable roles
- Provider/resource architecture and threat model with least privilege
- Off-host encrypted immutable backup and independently accessible keys
- Live monitoring dashboards/alerts plus incident tabletop exercise
- Verified restore into a **different** isolated non-production environment
- Actual cutover and rollback rehearsal with measured RTO and restore-point
  age relative to declared RPO
- Versioned schema, application and identity-provider health checks
- External security/data governance approval before handling sensitive data

For the CI-only proof of concept see
[disposable Postgres recovery drill](disposable-postgres-recovery-drill.md).
For the procedure see [backup and recovery runbook](backup-recovery-runbook.md).
Issue #38 stays open until deployed controls and realistic exercises are
independently verified.
