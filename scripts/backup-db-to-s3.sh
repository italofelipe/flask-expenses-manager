#!/usr/bin/env bash
# backup-db-to-s3.sh — Backup PostgreSQL → S3
#
# Executes pg_dump inside the running Docker container and uploads a gzipped
# dump to s3://auraxis-db-backups/daily/YYYY-MM-DD.sql.gz
#
# Usage:
#   bash scripts/backup-db-to-s3.sh
#
# Dependencies:
#   - docker CLI (auraxis-db-1 container must be running)
#   - aws CLI (EC2 instance role must have s3:PutObject on auraxis-db-backups)
#   - /opt/auraxis/.env.prod must define POSTGRES_USER, POSTGRES_DB, POSTGRES_PASSWORD
#
# Exit codes:
#   0  — success
#   1  — backup failed (pg_dump error)
#   2  — upload failed (aws s3 cp error)
#   3  — env validation failed

set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────────
BUCKET="auraxis-db-backups"
CONTAINER="auraxis-db-1"
ENV_FILE="${ENV_FILE:-/opt/auraxis/.env.prod}"
DATE=$(date -u +%Y-%m-%d)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DUMP_FILE="/tmp/auraxis-db-backup-${DATE}.sql.gz"
S3_KEY="daily/${DATE}.sql.gz"
LOG_PREFIX="[auraxis-backup]"

log()  { echo "${LOG_PREFIX} ${TIMESTAMP} INFO  $*"; }
warn() { echo "${LOG_PREFIX} ${TIMESTAMP} WARN  $*" >&2; }
fail() { echo "${LOG_PREFIX} ${TIMESTAMP} ERROR $*" >&2; exit "${1}"; }

# ── Validate environment ────────────────────────────────────────────────────
log "Loading env from ${ENV_FILE}"
if [[ ! -f "${ENV_FILE}" ]]; then
  fail 3 "Env file not found: ${ENV_FILE}"
fi

# Source only the variables we need; avoid polluting shell with all secrets
POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "${ENV_FILE}" | cut -d= -f2 | tr -d '"' | tr -d "'")
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "${ENV_FILE}" | cut -d= -f2 | tr -d '"' | tr -d "'")
POSTGRES_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' "${ENV_FILE}" | cut -d= -f2 | tr -d '"' | tr -d "'")

if [[ -z "${POSTGRES_USER}" || -z "${POSTGRES_DB}" || -z "${POSTGRES_PASSWORD}" ]]; then
  fail 3 "Missing POSTGRES_USER / POSTGRES_DB / POSTGRES_PASSWORD in ${ENV_FILE}"
fi

log "Database: ${POSTGRES_DB} | User: ${POSTGRES_USER} | Container: ${CONTAINER}"

# ── Validate container ──────────────────────────────────────────────────────
if ! docker ps --filter "name=${CONTAINER}" --filter "status=running" --quiet | grep -q .; then
  fail 1 "Container ${CONTAINER} is not running. Aborting backup."
fi

# ── Run pg_dump ─────────────────────────────────────────────────────────────
log "Starting pg_dump → ${DUMP_FILE}"
if ! docker exec \
  -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  "${CONTAINER}" \
  pg_dump \
    --username="${POSTGRES_USER}" \
    --dbname="${POSTGRES_DB}" \
    --format=plain \
    --no-password \
  | gzip > "${DUMP_FILE}"; then
  fail 1 "pg_dump failed. Check Docker logs: docker logs ${CONTAINER}"
fi

DUMP_SIZE=$(du -sh "${DUMP_FILE}" | cut -f1)
log "Dump complete. Size: ${DUMP_SIZE}"

# ── Upload to S3 ─────────────────────────────────────────────────────────────
log "Uploading to s3://${BUCKET}/${S3_KEY}"
if ! aws s3 cp "${DUMP_FILE}" "s3://${BUCKET}/${S3_KEY}" \
  --storage-class STANDARD_IA \
  --metadata "timestamp=${TIMESTAMP},database=${POSTGRES_DB},host=$(hostname)"; then
  rm -f "${DUMP_FILE}"
  fail 2 "S3 upload failed. Check IAM role has s3:PutObject on ${BUCKET}."
fi

log "Upload complete: s3://${BUCKET}/${S3_KEY}"

# ── Verify upload ────────────────────────────────────────────────────────────
S3_SIZE=$(aws s3 ls "s3://${BUCKET}/${S3_KEY}" --human-readable | awk '{print $3, $4}')
log "S3 object size: ${S3_SIZE}"

# ── Cleanup ───────────────────────────────────────────────────────────────────
rm -f "${DUMP_FILE}"
log "Temporary file removed"

# ── Summary ──────────────────────────────────────────────────────────────────
log "Backup successful: s3://${BUCKET}/${S3_KEY} (${DUMP_SIZE} compressed)"
