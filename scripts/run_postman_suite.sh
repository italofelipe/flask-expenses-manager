#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTION="${ROOT_DIR}/api-tests/postman/auraxis.postman_collection.json"
ENV_FILE_DEFAULT="${ROOT_DIR}/api-tests/postman/environments/local.postman_environment.json"
ENV_FILE="${1:-$ENV_FILE_DEFAULT}"
REPORT_DIR="${ROOT_DIR}/reports"
REPORT_FILE="${REPORT_DIR}/newman-report.xml"
TEST_PASSWORD="${POSTMAN_TEST_PASSWORD:-StrongPass@123}"
TEST_PASSWORD_WRONG="${POSTMAN_TEST_PASSWORD_WRONG:-WrongPass@123}"
ENABLE_PRIVILEGED_FLOWS="${POSTMAN_ENABLE_PRIVILEGED_FLOWS:-false}"
ADMIN_TOKEN="${POSTMAN_ADMIN_TOKEN:-}"

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found in PATH." >&2
  echo "Install Node.js/npm first." >&2
  exit 127
fi

if ! npx --no-install newman --version >/dev/null 2>&1; then
  echo "newman not available from local dependencies." >&2
  echo "Run: npm ci" >&2
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

NEWMAN_ARGS=(
  run "$COLLECTION"
  -e "$ENV_FILE"
  --env-var "testPassword=${TEST_PASSWORD}"
  --env-var "testPasswordWrong=${TEST_PASSWORD_WRONG}"
  --env-var "enablePrivilegedFlows=${ENABLE_PRIVILEGED_FLOWS}"
  --timeout-request 15000
  --delay-request 150
  --reporters cli,junit
  --reporter-junit-export "$REPORT_FILE"
)

if [[ -n "$ADMIN_TOKEN" ]]; then
  NEWMAN_ARGS+=(--env-var "adminToken=${ADMIN_TOKEN}")
fi

npx --no-install newman "${NEWMAN_ARGS[@]}"

echo "[postman-suite] report=$REPORT_FILE"
