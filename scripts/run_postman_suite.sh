#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTION="${ROOT_DIR}/api-tests/postman/auraxis.postman_collection.json"
ENV_FILE_DEFAULT="${ROOT_DIR}/api-tests/postman/environments/local.postman_environment.json"
ENV_FILE="${1:-$ENV_FILE_DEFAULT}"
REPORT_DIR="${ROOT_DIR}/reports"
REPORT_FILE="${REPORT_DIR}/newman-report.xml"

read_base_url_from_env_file() {
  python - "$ENV_FILE" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

for item in data.get("values", []):
    if item.get("key") == "baseUrl":
        print(item.get("value", "").rstrip("/"))
        break
PY
}

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

BASE_URL="${POSTMAN_BASE_URL:-$(read_base_url_from_env_file)}"
if [[ -z "$BASE_URL" ]]; then
  echo "Unable to resolve baseUrl from environment file: $ENV_FILE" >&2
  exit 4
fi

HEALTHCHECK_URL="${POSTMAN_HEALTHCHECK_URL:-${BASE_URL}/healthz}"

for _ in {1..15}; do
  if curl -fsS "$HEALTHCHECK_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "$HEALTHCHECK_URL" >/dev/null 2>&1; then
  cat >&2 <<EOF
[postman-suite] API is not reachable at: $HEALTHCHECK_URL
[postman-suite] Start the local stack first (e.g. docker compose up -d db redis web).
EOF
  exit 5
fi

mkdir -p "$REPORT_DIR"

echo "[postman-suite] collection=$COLLECTION"
echo "[postman-suite] environment=$ENV_FILE"
echo "[postman-suite] base_url=$BASE_URL"

newman run "$COLLECTION" \
  -e "$ENV_FILE" \
  --timeout-request 15000 \
  --delay-request 150 \
  --reporters cli,junit \
  --reporter-junit-export "$REPORT_FILE"

echo "[postman-suite] report=$REPORT_FILE"
