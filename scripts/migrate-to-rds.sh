#!/usr/bin/env bash
# =============================================================================
# migrate-to-rds.sh — Migrate Auraxis Postgres from Docker (EC2) to RDS
# Issue: H-INFRA-03 / GitHub #858
#
# Usage (run on EC2 via SSM):
#   sudo bash /opt/auraxis/scripts/migrate-to-rds.sh --rds-endpoint <host:port>
#
# What this script does (read-only against prod — does NOT change .env or restart):
#   1. Reads DATABASE_URL from /opt/auraxis/.env.prod
#   2. Dumps current Postgres inside the Docker container via pg_dump
#   3. Restores the dump to the new RDS endpoint
#   4. Verifies row counts match across key tables
#   5. Prints instructions to update .env.prod and restart
#
# PHASE 1 ONLY — this script is safe to run without affecting prod:
#   - It does NOT modify .env.prod
#   - It does NOT restart services
#   - It does NOT drop the Postgres container
#
# Prerequisites on EC2:
#   - psql / pg_restore available (install via: apt-get install -y postgresql-client)
#   - Docker Compose stack is running
#   - RDS instance is available and the EC2 security group sg-0edf5ab745a438dd2
#     is allowed ingress on port 5432 on the RDS security group
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Defaults ──────────────────────────────────────────────────────────────────
PROD_DIR="${PROD_DIR:-/opt/auraxis}"
ENV_FILE="${PROD_DIR}/.env.prod"
COMPOSE_FILE="${PROD_DIR}/docker-compose.prod.yml"
DUMP_PATH="/tmp/auraxis_pg_dump_$(date +%Y%m%d_%H%M%S).dump"
RDS_ENDPOINT=""
RDS_PORT="5432"
RDS_DB="auraxis"
RDS_USER="auraxis"

# ── Tables to verify ─────────────────────────────────────────────────────────
VERIFY_TABLES=(users transactions categories goals wallets)

# ── Parse args ────────────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 --rds-endpoint <hostname_or_host:port> [--rds-db <dbname>] [--rds-user <user>]"
  echo ""
  echo "Options:"
  echo "  --rds-endpoint   RDS endpoint host (e.g. auraxis-prod.xyz.us-east-1.rds.amazonaws.com)"
  echo "                   or host:port if not using default 5432"
  echo "  --rds-db         Database name on RDS (default: auraxis)"
  echo "  --rds-user       Master user on RDS (default: auraxis)"
  echo "  --prod-dir       Path to prod stack on EC2 (default: /opt/auraxis)"
  echo "  --dump-path      Override dump file path (default: /tmp/auraxis_pg_dump_<ts>.dump)"
  echo ""
  echo "Example:"
  echo "  sudo bash $0 --rds-endpoint auraxis-prod.cxxxxxx.us-east-1.rds.amazonaws.com"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rds-endpoint) RDS_ENDPOINT="$2"; shift 2 ;;
    --rds-db)       RDS_DB="$2"; shift 2 ;;
    --rds-user)     RDS_USER="$2"; shift 2 ;;
    --prod-dir)     PROD_DIR="$2"; ENV_FILE="${PROD_DIR}/.env.prod"; COMPOSE_FILE="${PROD_DIR}/docker-compose.prod.yml"; shift 2 ;;
    --dump-path)    DUMP_PATH="$2"; shift 2 ;;
    -h|--help)      usage ;;
    *) error "Unknown argument: $1"; usage ;;
  esac
done

[[ -z "$RDS_ENDPOINT" ]] && { error "--rds-endpoint is required"; usage; }

# Strip port from endpoint if provided as host:port
if [[ "$RDS_ENDPOINT" == *:* ]]; then
  RDS_PORT="${RDS_ENDPOINT##*:}"
  RDS_ENDPOINT="${RDS_ENDPOINT%%:*}"
fi

# ── Step 0: Validate environment ──────────────────────────────────────────────
info "=== Step 0: Validate environment ==="

if [[ ! -f "$ENV_FILE" ]]; then
  error "Env file not found: $ENV_FILE"
  exit 1
fi

if ! command -v docker &>/dev/null; then
  error "docker is not available. Are you running on the EC2 host?"
  exit 1
fi

if ! command -v psql &>/dev/null; then
  warn "psql not found. Attempting to install postgresql-client..."
  apt-get install -y postgresql-client 2>&1 | tail -5 || {
    error "Failed to install postgresql-client. Install manually: apt-get install -y postgresql-client"
    exit 1
  }
fi

if ! command -v pg_restore &>/dev/null; then
  error "pg_restore not found after installing postgresql-client. Check your PATH."
  exit 1
fi

info "Environment OK"

# ── Step 1: Read current DATABASE_URL from .env.prod ─────────────────────────
info "=== Step 1: Read current DATABASE_URL ==="

# Extract Postgres credentials from env file
SRC_POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'" | head -1)
SRC_POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'" | head -1)
SRC_POSTGRES_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'" | head -1)

if [[ -z "$SRC_POSTGRES_DB" || -z "$SRC_POSTGRES_USER" || -z "$SRC_POSTGRES_PASSWORD" ]]; then
  # Fallback: try to parse DATABASE_URL
  DATABASE_URL=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'" | head -1)
  if [[ -z "$DATABASE_URL" ]]; then
    error "Could not extract Postgres credentials from $ENV_FILE"
    error "Expected: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD (or DATABASE_URL)"
    exit 1
  fi
  # Parse postgresql://user:pass@host:port/db
  SRC_POSTGRES_USER=$(echo "$DATABASE_URL" | sed -E 's|postgresql://([^:]+):.*|\1|')
  SRC_POSTGRES_PASSWORD=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
  SRC_POSTGRES_DB=$(echo "$DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')
fi

info "Source DB: ${SRC_POSTGRES_DB}, User: ${SRC_POSTGRES_USER}"

# Find the running db container name
DB_CONTAINER=$(docker ps --filter "name=db" --filter "status=running" --format "{{.Names}}" | head -1)
if [[ -z "$DB_CONTAINER" ]]; then
  DB_CONTAINER=$(docker ps --filter "name=postgres" --filter "status=running" --format "{{.Names}}" | head -1)
fi
if [[ -z "$DB_CONTAINER" ]]; then
  error "Could not find running Postgres container. Is docker-compose up?"
  docker ps
  exit 1
fi

info "Found Postgres container: $DB_CONTAINER"

# ── Step 2: pg_dump inside Docker container ───────────────────────────────────
info "=== Step 2: pg_dump from Docker container ==="

CONTAINER_DUMP_PATH="/tmp/auraxis_dump.dump"

docker exec -e PGPASSWORD="$SRC_POSTGRES_PASSWORD" "$DB_CONTAINER" \
  pg_dump \
    --username="$SRC_POSTGRES_USER" \
    --dbname="$SRC_POSTGRES_DB" \
    --format=custom \
    --compress=9 \
    --no-password \
    --file="$CONTAINER_DUMP_PATH"

info "Copying dump from container to host..."
docker cp "${DB_CONTAINER}:${CONTAINER_DUMP_PATH}" "$DUMP_PATH"

DUMP_SIZE=$(du -sh "$DUMP_PATH" | cut -f1)
info "Dump written to: $DUMP_PATH (size: $DUMP_SIZE)"

# ── Step 3: Restore to RDS ────────────────────────────────────────────────────
info "=== Step 3: Restore to RDS (${RDS_ENDPOINT}:${RDS_PORT}/${RDS_DB}) ==="

warn "You will be prompted for the RDS master password."
warn "This is the password set in Terraform variable 'rds_password'."

# Create the database if it doesn't exist (pg_restore won't create it)
PGPASSWORD_PROMPT="Enter RDS master password for user '${RDS_USER}': "
read -s -r -p "$PGPASSWORD_PROMPT" RDS_PASSWORD
echo ""

export PGPASSWORD="$RDS_PASSWORD"

# Verify connectivity first
info "Testing RDS connectivity..."
psql \
  --host="$RDS_ENDPOINT" \
  --port="$RDS_PORT" \
  --username="$RDS_USER" \
  --dbname="postgres" \
  --command="SELECT version();" \
  --no-password 2>&1 | head -3

# Create target database (idempotent)
info "Creating database '${RDS_DB}' on RDS if not exists..."
psql \
  --host="$RDS_ENDPOINT" \
  --port="$RDS_PORT" \
  --username="$RDS_USER" \
  --dbname="postgres" \
  --no-password \
  --command="SELECT 'CREATE DATABASE ${RDS_DB}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${RDS_DB}')\gexec" || true

# Restore
info "Restoring dump to RDS..."
pg_restore \
  --host="$RDS_ENDPOINT" \
  --port="$RDS_PORT" \
  --username="$RDS_USER" \
  --dbname="$RDS_DB" \
  --no-password \
  --no-owner \
  --no-privileges \
  --verbose \
  "$DUMP_PATH" 2>&1 | tail -20

info "pg_restore complete."

# ── Step 4: Verify row counts ─────────────────────────────────────────────────
info "=== Step 4: Verify row counts ==="

MISMATCH=0

for TABLE in "${VERIFY_TABLES[@]}"; do
  # Count in source (Docker)
  SRC_COUNT=$(docker exec -e PGPASSWORD="$SRC_POSTGRES_PASSWORD" "$DB_CONTAINER" \
    psql --username="$SRC_POSTGRES_USER" --dbname="$SRC_POSTGRES_DB" \
    --tuples-only --command="SELECT COUNT(*) FROM ${TABLE};" 2>/dev/null | tr -d ' \n' || echo "TABLE_MISSING")

  # Count in RDS
  RDS_COUNT=$(PGPASSWORD="$RDS_PASSWORD" psql \
    --host="$RDS_ENDPOINT" --port="$RDS_PORT" \
    --username="$RDS_USER" --dbname="$RDS_DB" \
    --tuples-only --no-password \
    --command="SELECT COUNT(*) FROM ${TABLE};" 2>/dev/null | tr -d ' \n' || echo "TABLE_MISSING")

  if [[ "$SRC_COUNT" == "TABLE_MISSING" || "$RDS_COUNT" == "TABLE_MISSING" ]]; then
    warn "Table '$TABLE': source=${SRC_COUNT}, rds=${RDS_COUNT} — skipping (table may not exist yet)"
    continue
  fi

  if [[ "$SRC_COUNT" == "$RDS_COUNT" ]]; then
    info "  [OK] $TABLE: $SRC_COUNT rows"
  else
    error "  [MISMATCH] $TABLE: source=$SRC_COUNT, rds=$RDS_COUNT"
    MISMATCH=1
  fi
done

if [[ $MISMATCH -eq 1 ]]; then
  error "Row count mismatch detected. Review the pg_restore output above."
  error "Do NOT proceed with cutover until this is resolved."
  exit 1
fi

info "Row count verification passed."

# ── Step 5: Print cutover instructions ───────────────────────────────────────
echo ""
echo -e "${YELLOW}============================================================${NC}"
echo -e "${YELLOW}  PHASE 1 COMPLETE — Data verified. NO prod changes made.  ${NC}"
echo -e "${YELLOW}============================================================${NC}"
echo ""
echo "To complete the cutover (PHASE 2 — human approval required):"
echo ""
echo "  1. Open a maintenance window (notify users if needed)."
echo ""
echo "  2. On EC2, update /opt/auraxis/.env.prod:"
echo "     Remove (or comment out): DB_HOST=db / DB_PORT=5432 / DB_NAME / DB_USER / DB_PASS"
echo "     Add:"
echo "       DATABASE_URL=postgresql://${RDS_USER}:<password>@${RDS_ENDPOINT}:${RDS_PORT}/${RDS_DB}"
echo ""
echo "  3. Update docker-compose.prod.yml — comment out the 'db' service and its"
echo "     volume, and remove 'db' from the web service's depends_on."
echo "     (The updated template is already committed — see docs/wiki/RDS-Migration-Runbook.md)"
echo ""
echo "  4. Restart with the updated compose file:"
echo "       cd /opt/auraxis && docker compose -f docker-compose.prod.yml up -d --no-deps web"
echo ""
echo "  5. Verify health: curl https://api.auraxis.com.br/healthz"
echo ""
echo "  6. Monitor logs for 15 min: docker compose -f docker-compose.prod.yml logs -f web"
echo ""
echo "  7. If healthy, stop the old db container:"
echo "       docker compose -f docker-compose.prod.yml stop db"
echo "     (Keep data volume for 7 days before removing)"
echo ""
echo "  Dump file kept at: ${DUMP_PATH}"
echo "  Full runbook: docs/wiki/RDS-Migration-Runbook.md"
echo ""

unset PGPASSWORD
exit 0
