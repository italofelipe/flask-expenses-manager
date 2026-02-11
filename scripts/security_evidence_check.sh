#!/usr/bin/env bash
set -euo pipefail

REPORT_DIR="reports/security"
REPORT_FILE="${REPORT_DIR}/security-evidence.md"

mkdir -p "${REPORT_DIR}"

pass_count=0
fail_count=0

check_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if [[ -f "$file" ]] && grep -qE "$pattern" "$file"; then
    echo "- [PASS] ${label}" >>"${REPORT_FILE}"
    pass_count=$((pass_count + 1))
  else
    echo "- [FAIL] ${label}" >>"${REPORT_FILE}"
    fail_count=$((fail_count + 1))
  fi
}

check_exists() {
  local path="$1"
  local label="$2"

  if [[ -e "$path" ]]; then
    echo "- [PASS] ${label}" >>"${REPORT_FILE}"
    pass_count=$((pass_count + 1))
  else
    echo "- [FAIL] ${label}" >>"${REPORT_FILE}"
    fail_count=$((fail_count + 1))
  fi
}

{
  echo "# Security Evidence Report"
  echo
  echo "Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo
  echo "## OWASP S3 baseline artifacts"
} >"${REPORT_FILE}"

check_exists "docs/OWASP_S3_BASELINE.md" "OWASP baseline document exists"
check_exists "docs/OWASP_S3_INVENTORY.md" "OWASP inventory document exists"
check_exists "docs/OWASP_S3_CHECKLIST.md" "OWASP checklist document exists"

{
  echo
  echo "## Transport and proxy controls"
} >>"${REPORT_FILE}"

check_contains "deploy/nginx/default.tls.conf" "listen 443" "Nginx TLS listener configured"
check_contains "deploy/nginx/default.tls.conf" "ssl_protocols TLSv1\.2 TLSv1\.3" "TLS protocol baseline enforced"
check_contains "deploy/nginx/default.tls.conf" "Strict-Transport-Security" "HSTS header configured"
check_contains "deploy/nginx/default.tls.conf" "X-Frame-Options" "X-Frame-Options header configured"
check_contains "deploy/nginx/default.tls.conf" "X-Content-Type-Options" "X-Content-Type-Options header configured"

{
  echo
  echo "## API security controls"
} >>"${REPORT_FILE}"

check_contains "app/controllers/graphql_controller.py" "Campo 'query' é obrigatório" "GraphQL rejects empty query payload"
check_contains "app/graphql/security.py" "GRAPHQL_DEPTH_LIMIT_EXCEEDED" "GraphQL depth limit guard implemented"
check_contains "app/graphql/security.py" "GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED" "GraphQL complexity limit guard implemented"
check_contains "app/middleware/auth_guard.py" "verify_jwt_in_request\(\)" "Global auth guard verifies JWT for protected routes"
check_contains "app/controllers/auth_controller.py" "generate_password_hash" "Password hashing present for user registration"

if command -v rg >/dev/null 2>&1; then
  jwt_count=$(rg -n "@jwt_required\(" app/controllers | wc -l | tr -d ' ')
else
  jwt_count=$(grep -R --line-number "@jwt_required(" app/controllers | wc -l | tr -d ' ')
fi
if [[ "${jwt_count}" -gt 10 ]]; then
  echo "- [PASS] jwt_required coverage baseline (${jwt_count} protected handlers found)" >>"${REPORT_FILE}"
  pass_count=$((pass_count + 1))
else
  echo "- [FAIL] jwt_required coverage baseline (${jwt_count} protected handlers found)" >>"${REPORT_FILE}"
  fail_count=$((fail_count + 1))
fi

{
  echo
  echo "## Summary"
  echo
  echo "- Passed checks: ${pass_count}"
  echo "- Failed checks: ${fail_count}"
} >>"${REPORT_FILE}"

cat "${REPORT_FILE}"

if [[ "${fail_count}" -gt 0 ]]; then
  echo "Security evidence checks failed (${fail_count})."
  exit 1
fi

echo "Security evidence checks passed (${pass_count})."
