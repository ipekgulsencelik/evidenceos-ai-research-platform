# EvidenceOS PostgreSQL backup/recovery operator runbook (design only)

**Not executable against production.** No hosting provider, object storage,
KMS, RPO/RTO, retained backup schedule or incident approvers are selected
yet. Do not paste CI or development Compose commands into a production
host. This checklist must be revised for the chosen provider and tested by
two authorized operators before any customer/research data are stored.

## 0. Authority and readiness

The backup owner is responsible for routine backups and freshness alerts.
The on-call incident lead coordinates recovery; an independent security
approver authorizes access to recovery credentials and final cutover.
The data custodian decides whether retention, privacy and legal obligations
allow copying data into the proposed recovery region.

Before invoking this process, identify (in a private change record):

- The affected environment, the incident ticket, initial diagnosis,
  source cluster identity and approved restore **target** identity
- Target RPO/RTO, snapshot inventory and relevant WAL archives, supported
  PostgreSQL major version, expected extensions and migration revision
- Responsible backup operator, recovery operator, independent approver,
  isolation/network plan, backup-key break-glass path and escalation channel
- Whether external research provider uploads, Keycloak state, Redis sessions
  and attachments/object stores require separate restoration

**Fail closed:** No verified backup, no authorized independent recovery
target, no managed key access, or no approved change record means no
cutover. Do not bypass application RBAC, OIDC, Redis or auditing.

## 1. Prepare and select recovery point — read-only operations

1. Announce the incident and contain credential compromise if suspected.
   Preserve the old PostgreSQL cluster and its logs. Pause writes through
   controlled ingress or a maintenance gate; never delete data to "clean up".
2. Query the independent backup catalog *read-only*: last successful
   snapshots, archive continuity, integrity evidence, immutable retention,
   and encryption key recoverability. Do not treat a green scheduler job
   as evidence of a restorable archive.
3. Choose the newest **verified** point before the damage timestamp
   (including PITR target as needed). Record source record time,
   recovery point time, calculated data-loss window and expected RPO
   deviation. Determine legal/operational approval if target RPO is exceeded.
4. Obtain independent approval for a **new** isolated restoration target.
   Use a distinct resource name, account/project, private network and
   separate credentials. Enforce no outbound traffic to sensitive external
   providers during validation.

## 2. Restore only into a *new* resource

1. The environment-specific recovery playbook must prove target creation
   is new and **empty**; reject any existing or unknown database identifier.
   Provision only from a trusted PostgreSQL 16-compatible image/service,
   with matching locale, extensions, encryption, and target access rules.
2. Release the immutable snapshot and WAL archives to the restore principal
   using time-limited, audited grants. Never copy keys into command-line
   arguments, environment dumps, issue comments or shared CI artifacts.
3. Execute provider-specific restore/PITR into that isolated target and
   collect redacted job logs. Stop immediately on integrity, authentication
   or migration errors. Never run `pg_restore --clean` against the source.
4. Verify the restored database is internally consistent and that any
   target-specific identity/permissions are applied **after** restore
   without broad grants. Restore infrastructure resource bindings
   separately from application research records.
5. Keep the original system untouched until the recovery result is signed
   off. A CI synthetic restore success is **not** authorization to operate
   on production datasets.

## 3. Application and data checks — before cutover

- Verify expected schema revision (Alembic `head`), constraints, indexes,
  extension versions and project/membership/decision audit table presence.
- Compare project counts, related literature, quality review history,
  membership role distributions and immutable access audit continuity
  against approved manifests/checkpoints. Use privacy-safe checksums and
  aggregate counts; do not paste research content into logs.
- Start a **restricted, non-public** instance of the API/BFF against the
  restored target. Check health, create/read/list paths with synthetic
  probes, project owner/reviewer/outsider role isolation, CSRF protection
  and error handling. Do not use real end-user sessions.
- Keycloak issuer/JWKS, client redirect origins and logout URLs must
  match the environment; do not duplicate production IdP secrets into a
  development stack. Revoke/recreate affected sessions; keep unverified
  Redis sessions rejected. Recheck rate-limiter fail-closed behavior.
- Record elapsed recovery time from declared incident start to simulated
  safe service return, and compute the time gap between incident and
  restored data. Compare against target RTO/RPO, including the approval,
  DNS/ingress change, and user-session recovery times.

## 4. Controlled cutover and rollback

The independent approver reviews data integrity, privacy, role tests,
app health, alerting, measured recovery objectives and any data loss.
Only after written sign-off may operations switch upstreams via the
approved release/change procedure with restricted credentials.

Watch DB health, API latency/5xx, authorization denials, rate-limit
429/503, queue/backpressure, and audit events. Keep the old environment
quarantined and available for rollback/investigation, not writable in
parallel. If checks regress, stop traffic and follow the preapproved
rollback plan; preserve incident evidence.

Do not assume that switching DNS restores identity-provider sessions,
Redis revocation lists or uploaded binary artifacts.

## 5. Close incident and improve controls

- Document exact recovery point, data-loss estimate, recovery duration,
  production changes, independently verified integrity evidence and
  sign-off. Handle personal/research content only in protected systems.
- Rotate compromised credentials and issue new least-privilege policies.
  Confirm immutable backup retention, key recovery and backup freshness
  alerts are still effective.
- Conduct follow-up review for missing WAL, failed restore steps, orphaned
  external resources, security exposure and preventive actions.
- Add redacted exercise evidence to a private operations system.
  Never upload databases, SQL dumps, encryption keys or password values
  to GitHub Actions artifacts or issue threads.

## Planned test matrix before pilot

| Test scenario | Pass criterion |
| --- | --- |
| Ordinary restore of newest clean point | Data and migration checks pass on a different target |
| Tampered snapshot/failed checksum | Reject archive, do not cut over |
| Missing WAL segment | Alert; independently determine nearest recoverable point |
| Backup job stale or off-host store inaccessible | Alert and incident handling without unsafe fallback |
| Restore principal lacks decrypt grant | Deny; execute reviewed break-glass recovery |
| Redis/Keycloak outage during recovery | No authorization bypass, and unknown session rejected |
| New recovery target fails RBAC/audit checks | Do not cut over; retain original system |
| Repeated drill with representative dataset | Recorded restore duration, actual loss window, RPO/RTO compliance |
| Rollback after cutover simulation | Restore previous service safely without conflicting writes |

The repository's disposable CI exercise demonstrates only a very small
subset of these scenarios, with **synthetic** records. The complete
production-like drill, monitoring, retention and key recovery are still
open in Issue #38.
