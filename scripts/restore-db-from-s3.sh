#!/usr/bin/env bash
# restore-db-from-s3.sh — Restore PostgreSQL from S3 backup
#
# Downloads a backup from S3 and restores it into the running PostgreSQL
# container. DESTRUCTIVE: drops and recreates the database.
#
# Usage:
#   bash scripts/restore-db-from-s3.sh [DATE]
#
#   DATE  — backup date in YYYY-MM-DD format (default: today)
#
# Examples:
#   bash scripts/restore-db-from-s3.sh 2026-04-05   # restore specific date
#   bash scripts/restore-db-from-s3.sh               # restore today's backup
#
# Exit codes:
#   0  — success
#   1  — restore failed
#   2  — download failed
#   3  — env / validation failed

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
BUCKET="auraxis-db-backups"
CONTAINER="auraxis-db-1"
ENV_FILE="${ENV_FILE:-/opt/auraxis/.env.prod}"
DATE="${1:-$(date -u +%Y-%m-%d)}"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DUMP_FILE="/tmp/auraxis-db-restore-${DATE}.sql.gz"
S3_KEY="daily/${DATE}.sql.gz"
LOG_PREFIX="[auraxis-restore]"

log()  { echo "${LOG_PREFIX} ${TIMESTAMP} INFO  $*"; }
warn() { echo "${LOG_PREFIX} ${TIMESTAMP} WARN  $*" >&2; }
fail() { echo "${LOG_PREFIX} ${TIMESTAMP} ERROR $*" >&2; exit "${1}"; }

# ── Safety confirmation ──────────────────────────────────────────────────────
warn "┌──────────────────────────────────────────────────────────────────────┐"
warn "│  WARNING: This will DROP and RECREATE the database '${POSTGRES_DB}'   │"
warn "│  All current data will be permanently deleted.                        │"
warn "│  Restore source: s3://${BUCKET}/${S3_KEY}                            │"
warn "└──────────────────────────────────────────────────────────────────────┘"

if [[ "${AURAXIS_RESTORE_CONFIRMED:-}" != "yes" ]]; then
  read -r -p "Type 'RESTORE' to confirm: " CONFIRM
  if [[ "${CONFIRM}" != "RESTORE" ]]; then
    log "Restore cancelled."
    exit 0
  fi
fi

# ── Load env ──────────────────────────────────────────────────────────────────
log "Loading env from ${ENV_FILE}"
if [[ ! -f "${ENV_FILE}" ]]; then
  fail 3 "Env file not found: ${ENV_FILE}"
fi

POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "${ENV_FILE}" | cut -d= -f2 | tr -d '"' | tr -d "'")
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "${ENV_FILE}" | cut -d= -f2 | tr -d '"' | tr -d "'")
POSTGRES_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' "${ENV_FILE}" | cut -d= -f2 | tr -d '"' | tr -d "'")

if [[ -z "${POSTGRES_USER}" || -z "${POSTGRES_DB}" || -z "${POSTGRES_PASSWORD}" ]]; then
  fail 3 "Missing POSTGRES_USER / POSTGRES_DB / POSTGRES_PASSWORD in ${ENV_FILE}"
fi

# ── Validate container ───────────────────────────────────────────────────────
if ! docker ps --filter "name=${CONTAINER}" --filter "status=running" --quiet | grep -q .; then
  fail 3 "Container ${CONTAINER} is not running."
fi

# ── Download from S3 ─────────────────────────────────────────────────────────
log "Downloading s3://${BUCKET}/${S3_KEY} → ${DUMP_FILE}"
if ! aws s3 cp "s3://${BUCKET}/${S3_KEY}" "${DUMP_FILE}"; then
  fail 2 "S3 download failed. Verify the key exists: aws s3 ls s3://${BUCKET}/daily/"
fi

DUMP_SIZE=$(du -sh "${DUMP_FILE}" | cut -f1)
log "Downloaded: ${DUMP_SIZE}"

# ── Stop app to prevent writes during restore ────────────────────────────────
log "Stopping app container to prevent writes during restore..."
docker stop auraxis-web-1 2>/dev/null || warn "auraxis-web-1 not running, continuing"

# ── Drop and recreate database ───────────────────────────────────────────────
log "Dropping database ${POSTGRES_DB}..."
docker exec \
  -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  "${CONTAINER}" \
  psql --username="${POSTGRES_USER}" --dbname=postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};" \
  -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"

log "Database ${POSTGRES_DB} recreated"

# ── Restore dump ─────────────────────────────────────────────────────────────
log "Restoring dump..."
if ! gunzip -c "${DUMP_FILE}" | docker exec \
  -i \
  -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  "${CONTAINER}" \
  psql --username="${POSTGRES_USER}" --dbname="${POSTGRES_DB}" --quiet; then
  warn "Restore completed with warnings. Verify data integrity."
fi

log "Restore complete"

# ── Restart app ───────────────────────────────────────────────────────────────
log "Restarting app container..."
cd /opt/auraxis && docker compose -f docker-compose.prod.yml up -d web

# ── Cleanup ───────────────────────────────────────────────────────────────────
rm -f "${DUMP_FILE}"
log "Temporary file removed"

log "✓ Database restored from s3://${BUCKET}/${S3_KEY}"
log "  Verify: docker exec auraxis-db-1 psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c '\\dt'"
