#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTION="${ROOT_DIR}/api-tests/postman/auraxis.postman_collection.json"
ENV_FILE_DEFAULT="${ROOT_DIR}/api-tests/postman/environments/local.postman_environment.json"
ENV_FILE="${1:-$ENV_FILE_DEFAULT}"
REPORT_DIR="${ROOT_DIR}/reports"
REPORT_FILE="${REPORT_DIR}/newman-report.xml"

if ! command -v newman >/dev/null 2>&1; then
  echo "newman not found in PATH." >&2
  echo "Install with: npm install -g newman" >&2
  exit 127
fi

if [[ ! -f "$COLLECTION" ]]; then
  echo "Collection not found: $COLLECTION" >&2
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 3
fi

mkdir -p "$REPORT_DIR"

echo "[postman-suite] collection=$COLLECTION"
echo "[postman-suite] environment=$ENV_FILE"

newman run "$COLLECTION" \
  -e "$ENV_FILE" \
  --timeout-request 15000 \
  --delay-request 150 \
  --reporters cli,junit \
  --reporter-junit-export "$REPORT_FILE"

echo "[postman-suite] report=$REPORT_FILE"
