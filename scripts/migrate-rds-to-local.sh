#!/usr/bin/env bash
# scripts/migrate-rds-to-local.sh
#
# One-shot migration helper: pg_dump from RDS endpoint → restore into local
# Postgres container (`db` service in docker-compose.prod.yml).
#
# Step 2 of the RDS → self-hosted Postgres migration. See:
#   - ADR: auraxis-platform/.context/adr/rds_to_self_hosted_postgres.md
#   - Umbrella issue: #1376
#   - This script: closes #1378
#
# Designed to run on the prod EC2 (i-0057e3b52162f78f8) during the migration
# window (#1379), via SSM or interactive SSH. Also runnable locally for
# staging rehearsal.
#
# Behavior:
#   - Reads RDS endpoint + creds from the env file (default: /etc/auraxis/backup.env)
#   - Reads local-container creds from the same env file (POSTGRES_USER/DB/PASSWORD)
#   - Uses `docker exec auraxis-db-1` to run pg_dump and pg_restore so we don't
#     need pg_dump binary on the host
#   - pg_dump uses --no-owner --clean --if-exists to allow drop+recreate on restore
#   - Validates the dump size before restore (>1 KB minimum)
#   - Post-restore, runs `SELECT COUNT(*) FROM users` as a sanity check
#   - Idempotent in spirit: re-running is safe (DROP+CREATE), but the application
#     should be DOWN during the run to avoid mid-migration writes
#
# Required env (from /etc/auraxis/backup.env or shell):
#   AURAXIS_DB_HOST       — RDS endpoint (e.g. auraxis-prod.cav02gmeg759....rds.amazonaws.com)
#   AURAXIS_DB_PORT       — RDS port (5432)
#   AURAXIS_DB_NAME       — db name (auraxis)
#   AURAXIS_DB_USER       — db user (auraxis)
#   AURAXIS_DB_PASSWORD   — db password (same on both sides — see below)
#
# Optional env:
#   AURAXIS_DB_CONTAINER  — local Postgres container (default: auraxis-db-1)
#   AURAXIS_MIGRATION_TMPDIR — temp dir for the dump (default: /tmp)
#   AURAXIS_MIGRATION_KEEP_DUMP — if "1", keep the dump file (default: cleanup)
#   AURAXIS_MIGRATION_DRY_RUN — if "1", validate connectivity only (no dump/restore)
#
# Exit codes:
#   0  — success
#   1  — pre-flight failure (missing env, container not running, etc.)
#   2  — pg_dump failed
#   3  — pg_dump produced suspicious output (too small)
#   4  — restore failed
#   5  — post-restore validation failed
#
# Important: the local container's POSTGRES_PASSWORD must match the RDS
# password so the application's DATABASE_URL only needs the host changed.
# This is enforced by reusing the same .env.prod for both sides.

set -euo pipefail

ENV_FILE="${ENV_FILE:-/etc/auraxis/backup.env}"
LOCAL_CONTAINER="${AURAXIS_DB_CONTAINER:-auraxis-db-1}"
TMPDIR="${AURAXIS_MIGRATION_TMPDIR:-/tmp}"
KEEP_DUMP="${AURAXIS_MIGRATION_KEEP_DUMP:-0}"
DRY_RUN="${AURAXIS_MIGRATION_DRY_RUN:-0}"

TIMESTAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
DUMP_FILE="${TMPDIR}/auraxis-rds-migration-${TIMESTAMP}.sql"
LOG_PREFIX="[migrate-rds-to-local]"

log() {
  printf '%s %s %s\n' "$LOG_PREFIX" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

fail() {
  local code="$1"; shift
  log "ERROR (exit=$code): $*"
  if [[ "$KEEP_DUMP" != "1" && -f "$DUMP_FILE" ]]; then
    rm -f "$DUMP_FILE"
  fi
  exit "$code"
}

cleanup() {
  if [[ "$KEEP_DUMP" != "1" && -f "$DUMP_FILE" ]]; then
    rm -f "$DUMP_FILE" || true
  fi
}

# ── 0. Pre-flight ──────────────────────────────────────────────────────────────

if [[ ! -f "$ENV_FILE" ]]; then
  fail 1 "Env file not found: $ENV_FILE"
fi

# shellcheck source=/dev/null
set -a
. "$ENV_FILE"
set +a

for var in AURAXIS_DB_HOST AURAXIS_DB_PORT AURAXIS_DB_NAME AURAXIS_DB_USER AURAXIS_DB_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    fail 1 "Missing env: $var (load from $ENV_FILE)"
  fi
done

command -v docker >/dev/null 2>&1 || fail 1 "docker CLI not on PATH"

# Confirm local container is running
if ! docker ps --filter "name=${LOCAL_CONTAINER}" --filter "status=running" --quiet | grep -q .; then
  fail 1 "Local container ${LOCAL_CONTAINER} is not running. Start docker-compose.prod.yml db service first."
fi

# Confirm pg_isready works against the local container
if ! docker exec "$LOCAL_CONTAINER" pg_isready -U "$AURAXIS_DB_USER" >/dev/null 2>&1; then
  fail 1 "Local Postgres not ready inside ${LOCAL_CONTAINER}"
fi

log "Pre-flight OK. RDS=${AURAXIS_DB_HOST}, local=${LOCAL_CONTAINER}, db=${AURAXIS_DB_NAME}"

# Connectivity test to RDS (uses the local container's psql client)
log "Testing RDS connectivity..."
if ! docker exec \
  -e PGPASSWORD="$AURAXIS_DB_PASSWORD" \
  "$LOCAL_CONTAINER" \
  psql --host="$AURAXIS_DB_HOST" --port="$AURAXIS_DB_PORT" \
       --username="$AURAXIS_DB_USER" --dbname="$AURAXIS_DB_NAME" \
       --no-password --tuples-only --no-align \
       -c "SELECT 'ok'" 2>&1 | grep -q '^ok'; then
  fail 1 "Cannot connect to RDS endpoint ${AURAXIS_DB_HOST}"
fi

log "RDS connectivity OK"

if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY_RUN=1 — pre-flight only, exiting"
  cleanup
  exit 0
fi

# ── 1. pg_dump from RDS ────────────────────────────────────────────────────────

log "Starting pg_dump from RDS → ${DUMP_FILE}"

if ! docker exec \
  -e PGPASSWORD="$AURAXIS_DB_PASSWORD" \
  "$LOCAL_CONTAINER" \
  pg_dump --host="$AURAXIS_DB_HOST" --port="$AURAXIS_DB_PORT" \
          --username="$AURAXIS_DB_USER" --dbname="$AURAXIS_DB_NAME" \
          --no-password --no-owner --no-acl --clean --if-exists \
          --format=plain \
  > "$DUMP_FILE" 2>>/tmp/migrate-rds-pg_dump.err; then
  fail 2 "pg_dump failed. Tail of /tmp/migrate-rds-pg_dump.err: $(tail -5 /tmp/migrate-rds-pg_dump.err 2>/dev/null || echo '(no log)')"
fi

DUMP_SIZE="$(stat -c%s "$DUMP_FILE" 2>/dev/null || stat -f%z "$DUMP_FILE" 2>/dev/null || echo 0)"
if [[ "$DUMP_SIZE" -lt 1024 ]]; then
  fail 3 "Dump file is suspiciously small: ${DUMP_SIZE} bytes"
fi

log "pg_dump OK. Size=${DUMP_SIZE} bytes"

# ── 2. Restore into local container ────────────────────────────────────────────

log "Restoring dump into local container ${LOCAL_CONTAINER} db=${AURAXIS_DB_NAME}..."

# Pipe the dump into psql inside the container. Connect to `postgres` system
# database to allow DROP+CREATE of the target db.
if ! docker exec -i \
  -e PGPASSWORD="$AURAXIS_DB_PASSWORD" \
  "$LOCAL_CONTAINER" \
  psql --username="$AURAXIS_DB_USER" --dbname="$AURAXIS_DB_NAME" \
       --set ON_ERROR_STOP=on \
  < "$DUMP_FILE" >/tmp/migrate-rds-restore.log 2>&1; then
  fail 4 "Restore failed. Tail of /tmp/migrate-rds-restore.log: $(tail -10 /tmp/migrate-rds-restore.log 2>/dev/null || echo '(no log)')"
fi

log "Restore OK"

# ── 3. Post-restore sanity check ───────────────────────────────────────────────

# Count rows in users table (must exist and have at least 1 row for an active app)
USER_COUNT="$(docker exec \
  -e PGPASSWORD="$AURAXIS_DB_PASSWORD" \
  "$LOCAL_CONTAINER" \
  psql --username="$AURAXIS_DB_USER" --dbname="$AURAXIS_DB_NAME" \
       --tuples-only --no-align \
       -c "SELECT COUNT(*) FROM users" 2>/dev/null || echo "ERROR")"

if [[ "$USER_COUNT" == "ERROR" || ! "$USER_COUNT" =~ ^[0-9]+$ ]]; then
  fail 5 "Post-restore sanity check failed: cannot count users (got: ${USER_COUNT})"
fi

if [[ "$USER_COUNT" -lt 1 ]]; then
  log "WARN: 0 users post-restore — this is suspicious for an active prod DB, please verify manually"
fi

log "Sanity check OK: users count=${USER_COUNT}"

# Cross-check vs RDS user count (sanity that we copied the right data)
RDS_USER_COUNT="$(docker exec \
  -e PGPASSWORD="$AURAXIS_DB_PASSWORD" \
  "$LOCAL_CONTAINER" \
  psql --host="$AURAXIS_DB_HOST" --port="$AURAXIS_DB_PORT" \
       --username="$AURAXIS_DB_USER" --dbname="$AURAXIS_DB_NAME" \
       --no-password --tuples-only --no-align \
       -c "SELECT COUNT(*) FROM users" 2>/dev/null || echo "ERROR")"

if [[ "$RDS_USER_COUNT" =~ ^[0-9]+$ && "$RDS_USER_COUNT" != "$USER_COUNT" ]]; then
  log "WARN: row count mismatch! RDS users=${RDS_USER_COUNT}, local=${USER_COUNT}. Investigate before cutover."
fi

cleanup

log "DONE — migration successful. Next steps:"
log "  1. Update DATABASE_URL in /opt/auraxis/.env.prod to point to db:5432"
log "  2. Restart compose: docker compose --env-file .env.prod -f docker-compose.prod.yml up -d"
log "  3. Smoke test via curl + manual login"

exit 0
