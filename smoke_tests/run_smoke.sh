#!/bin/bash
# run_smoke.sh — Executes Newman smoke test suite against a live Auraxis API deployment.
# Usage: bash smoke_tests/run_smoke.sh
# Environment variables:
#   SMOKE_BASE_URL      — Base URL of the API (default: http://localhost:5000)
#   SMOKE_TEST_EMAIL    — Login e-mail for smoke test account (default: smoke@test.com)
#   SMOKE_TEST_PASSWORD — Password for smoke test account (default: smokepass)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

npx newman run "${SCRIPT_DIR}/auraxis_smoke.postman_collection.json" \
  --environment "${SCRIPT_DIR}/auraxis_smoke.postman_environment.json" \
  --env-var "base_url=${SMOKE_BASE_URL:-http://localhost:5000}" \
  --env-var "test_email=${SMOKE_TEST_EMAIL:-smoke@test.com}" \
  --env-var "test_password=${SMOKE_TEST_PASSWORD:-smokepass}" \
  --reporters cli,json \
  --reporter-json-export "${SCRIPT_DIR}/results.json"
