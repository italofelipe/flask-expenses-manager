#!/usr/bin/env bash
# install-backup-cron.sh — Install DB backup cron job on EC2
#
# Installs the backup script to /opt/auraxis/scripts/ and registers the
# cron job at /etc/cron.d/auraxis-db-backup (runs daily at 02:00 UTC).
#
# Must be run as root or with sudo.
#
# Usage:
#   sudo bash scripts/install-backup-cron.sh

set -euo pipefail

APP_DIR="/opt/auraxis"
SCRIPTS_DIR="${APP_DIR}/scripts"
BACKUP_SCRIPT="${SCRIPTS_DIR}/backup-db-to-s3.sh"
CRON_FILE="/etc/cron.d/auraxis-db-backup"
LOG_FILE="/var/log/auraxis-db-backup.log"
CRON_USER="root"

log() { echo "[install-backup-cron] $*"; }

# ── Validate ─────────────────────────────────────────────────────────────────
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "ERROR: Must run as root (use sudo)" >&2
  exit 1
fi

if [[ ! -f "${APP_DIR}/scripts/backup-db-to-s3.sh" ]]; then
  echo "ERROR: backup-db-to-s3.sh not found at ${APP_DIR}/scripts/" >&2
  echo "Run 'git pull' in ${APP_DIR} to get the latest scripts." >&2
  exit 1
fi

# ── Make executable ───────────────────────────────────────────────────────────
chmod +x "${BACKUP_SCRIPT}"
log "Made executable: ${BACKUP_SCRIPT}"

# ── Create log file ───────────────────────────────────────────────────────────
touch "${LOG_FILE}"
chmod 644 "${LOG_FILE}"
log "Log file: ${LOG_FILE}"

# ── Write cron job ────────────────────────────────────────────────────────────
cat > "${CRON_FILE}" <<EOF
# Auraxis — Daily PostgreSQL backup to S3
# Runs at 02:00 UTC every day
# Script: ${BACKUP_SCRIPT}
# Logs:   ${LOG_FILE}
# Bucket: s3://auraxis-db-backups/daily/
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

0 2 * * * ${CRON_USER} ${BACKUP_SCRIPT} >> ${LOG_FILE} 2>&1
EOF

chmod 644 "${CRON_FILE}"
log "Cron job installed: ${CRON_FILE}"

# ── Show result ───────────────────────────────────────────────────────────────
log ""
log "✓ Backup cron job installed successfully"
log ""
log "  Schedule: daily at 02:00 UTC"
log "  Script:   ${BACKUP_SCRIPT}"
log "  Cron:     ${CRON_FILE}"
log "  Logs:     ${LOG_FILE}"
log ""
log "To run a manual backup now:"
log "  sudo bash ${BACKUP_SCRIPT}"
log ""
log "To verify the cron entry:"
log "  cat ${CRON_FILE}"
