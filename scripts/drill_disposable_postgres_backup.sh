#!/usr/bin/env bash
# CI-ONLY synthetic PostgreSQL 16 backup/restore exercise.
# Never accepts external connection strings, container names, or backup paths.
set -Eeuo pipefail
umask 077

if [[ "${GITHUB_ACTIONS:-}" != "true" ||
      "${EVIDENCEOS_DRILL_CONFIRM:-}" != "isolated-synthetic-only" ]]; then
  echo "Refusing: disposable PostgreSQL drill is restricted to explicitly opted-in CI." >&2
  exit 2
fi
if [[ -n "${EVIDENCEOS_DATABASE_URL:-}" || -n "${DATABASE_URL:-}" ||
      -n "${PGHOST:-}" || -n "${PGDATABASE:-}" ]]; then
  echo "Refusing: an external PostgreSQL connection setting is present." >&2
  exit 2
fi
for binary in docker openssl gpg python3; do
  command -v "$binary" >/dev/null || { echo "Missing drill dependency." >&2; exit 2; }
done
docker image inspect evidenceos-api:ci >/dev/null 2>&1 || {
  echo "Build the CI-only EvidenceOS API image before the drill." >&2
  exit 2
}

suffix="$(openssl rand -hex 8)"
network="evidenceos-recovery-${suffix}"
source="evidenceos-recovery-source-${suffix}"
target="evidenceos-recovery-target-${suffix}"
database="evidenceos_drill"
dbuser="evidenceosdrill"
dbpass="$(openssl rand -hex 32)"
encryption_passphrase="$(openssl rand -hex 32)"
scratch="$(mktemp -d /tmp/evidenceos-pg-drill.XXXXXXXX)"
chmod 700 "$scratch"
mkdir -m 700 "$scratch/gnupg"
export GNUPGHOME="$scratch/gnupg"

cleanup() {
  docker rm -f "$source" "$target" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  # Only remove the newly created, tightly scoped CI temporary directory.
  case "$scratch" in
    /tmp/evidenceos-pg-drill.*) rm -rf -- "$scratch" ;;
  esac
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker network create --internal --label evidenceos.recovery.drill=true "$network" >/dev/null
docker image inspect postgres:16-alpine >/dev/null 2>&1 ||
  docker pull postgres:16-alpine >/dev/null

for container in "$source" "$target"; do
  docker run --rm -d --name "$container" --network "$network" \
    --label evidenceos.recovery.drill=true \
    -e "POSTGRES_DB=$database" -e "POSTGRES_USER=$dbuser" \
    -e "POSTGRES_PASSWORD=$dbpass" \
    postgres:16-alpine >/dev/null
done

ready() {
  local container="$1"
  for _attempt in {1..30}; do
    if docker exec "$container" pg_isready -U "$dbuser" -d "$database" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Disposable PostgreSQL instance did not become ready." >&2
  return 1
}
ready "$source"
ready "$target"

# The API image uses real, repository-managed Alembic migrations.
docker run --rm --network "$network" \
  -e "EVIDENCEOS_DATABASE_URL=postgresql+asyncpg://$dbuser:$dbpass@$source:5432/$database" \
  evidenceos-api:ci /app/.venv/bin/alembic upgrade head >/dev/null

# All records are synthetic fixed fixtures, never sampled from customer data.
docker exec -i "$source" psql -X -q -U "$dbuser" -d "$database" -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
INSERT INTO research_projects(id, title, domain, created_at) VALUES
 ('00000000-0000-4000-8000-000000000101', 'Synthetic recovery A', 'academic', now()),
 ('00000000-0000-4000-8000-000000000102', 'Synthetic recovery B', 'academic', now());
INSERT INTO project_memberships(project_id, principal_key, role, created_at) VALUES
 ('00000000-0000-4000-8000-000000000101', repeat('a', 64), 'owner', now()),
 ('00000000-0000-4000-8000-000000000101', repeat('b', 64), 'viewer', now());
INSERT INTO access_decision_events(id, actor_key, project_id, action, outcome, request_id, created_at) VALUES
 ('00000000-0000-4000-8000-000000000201', repeat('a', 64), '00000000-0000-4000-8000-000000000101', 'project.create', 'allowed', 'synthetic-drill-1', now()),
 ('00000000-0000-4000-8000-000000000202', repeat('b', 64), '00000000-0000-4000-8000-000000000101', 'project.read', 'denied', 'synthetic-drill-2', now());
SQL

# Always query solely the two randomly named, isolated Docker containers.
counts_sql="SELECT (SELECT count(*) FROM research_projects)::text || ':' ||
                   (SELECT count(*) FROM project_memberships)::text || ':' ||
                   (SELECT count(*) FROM access_decision_events)::text"
fingerprint_sql="SELECT md5(
  coalesce((SELECT string_agg(id::text || ':' || title || ':' || domain, '|' ORDER BY id) FROM research_projects), '') || '#' ||
  coalesce((SELECT string_agg(project_id::text || ':' || principal_key || ':' || role, '|' ORDER BY project_id, principal_key) FROM project_memberships), '') || '#' ||
  coalesce((SELECT string_agg(id::text || ':' || actor_key || ':' || action || ':' || outcome, '|' ORDER BY id) FROM access_decision_events), '')
)"
query() {
  docker exec "$1" psql -X -A -t -U "$dbuser" -d "$database" -v ON_ERROR_STOP=1 -c "$2"
}
source_counts="$(query "$source" "$counts_sql")"
source_fingerprint="$(query "$source" "$fingerprint_sql")"
source_migration="$(query "$source" "SELECT version_num FROM alembic_version")"
[[ "$source_counts" == "2:2:2" && -n "$source_migration" && -n "$source_fingerprint" ]] || {
  echo "Synthetic source integrity preflight failed." >&2; exit 1;
}

# Export a custom-format dump directly into an encrypted, authenticated
# OpenPGP archive. No unencrypted archive is persisted for backup storage.
docker exec "$source" pg_dump -U "$dbuser" -d "$database" \
  --format=custom --no-owner --no-acl --schema=public |
  gpg --batch --yes --quiet --pinentry-mode loopback \
    --passphrase-fd 3 --symmetric --cipher-algo AES256 \
    --output "$scratch/synthetic-backup.gpg" 3<<<"$encryption_passphrase"
[[ -s "$scratch/synthetic-backup.gpg" ]] || {
  echo "Encrypted backup missing." >&2; exit 1;
}
snapshot_at="$(date +%s)"

# Negative test: a modified encrypted archive must fail authentication.
python3 - "$scratch/synthetic-backup.gpg" "$scratch/tampered.gpg" <<'PY'
from pathlib import Path
import sys
data = bytearray(Path(sys.argv[1]).read_bytes())
if len(data) < 32:
    raise SystemExit("Encrypted archive is unexpectedly short")
data[-1] ^= 1
Path(sys.argv[2]).write_bytes(data)
PY
if gpg --batch --quiet --pinentry-mode loopback --passphrase-fd 3 \
  --decrypt "$scratch/tampered.gpg" >/dev/null 2>&1 3<<<"$encryption_passphrase"; then
  echo "Failed closed-check: modified encrypted archive was accepted." >&2
  exit 1
fi

# This plaintext is temporary synthetic test data, created only in isolated
# CI and deleted by the EXIT trap. Do NOT adapt this workflow for real data.
restore_start="$(date +%s)"
gpg --batch --quiet --pinentry-mode loopback --passphrase-fd 3 \
  --decrypt "$scratch/synthetic-backup.gpg" \
  > "$scratch/verified-synthetic.dump" 3<<<"$encryption_passphrase"
# A fresh PostgreSQL 16 database already owns an empty "public" schema.
# The custom-format archive also includes CREATE SCHEMA public. Drop ONLY
# this known-empty schema inside our uniquely named disposable target.
# Never perform a schema drop on the source or an externally supplied DB.
target_public_tables="$(query "$target" "SELECT count(*) FROM pg_tables WHERE schemaname='public'")"
[[ "$target_public_tables" == "0" ]] || {
  echo "Refusing restore: disposable target schema is not empty." >&2
  exit 1
}
docker exec "$target" psql -X -q -U "$dbuser" -d "$database" \
  -v ON_ERROR_STOP=1 -c "DROP SCHEMA public" >/dev/null
docker exec -i "$target" pg_restore --exit-on-error --no-owner --no-acl \
  -U "$dbuser" -d "$database" < "$scratch/verified-synthetic.dump" >/dev/null

target_counts="$(query "$target" "$counts_sql")"
target_fingerprint="$(query "$target" "$fingerprint_sql")"
target_migration="$(query "$target" "SELECT version_num FROM alembic_version")"
[[ "$target_counts" == "$source_counts" &&
   "$target_fingerprint" == "$source_fingerprint" &&
   "$target_migration" == "$source_migration" ]] || {
  echo "Restored synthetic database failed integrity verification." >&2
  exit 1
}
[[ "$(query "$source" "$counts_sql")" == "$source_counts" ]] || {
  echo "Original disposable source changed during restore." >&2
  exit 1
}
restore_seconds="$(( $(date +%s) - restore_start ))"
snapshot_age_seconds="$(( $(date +%s) - snapshot_at ))"
echo "DISPOSABLE_RECOVERY_DRILL_PASS projects=2 memberships=2 audit_events=2"
echo "Encrypted_archive=OpenPGP_AES256 tamper_rejected=true source_unchanged=true"
echo "Sample_restore_seconds=$restore_seconds sample_snapshot_age_seconds=$snapshot_age_seconds"
echo "These are CI-only synthetic sample times, NOT production RTO/RPO guarantees."
