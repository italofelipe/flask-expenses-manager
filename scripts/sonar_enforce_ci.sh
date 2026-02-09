#!/usr/bin/env bash
set -euo pipefail

SONAR_HOST_URL="${SONAR_HOST_URL:-https://sonarcloud.io}"

required_vars=(
  "SONAR_TOKEN"
  "SONAR_PROJECT_KEY"
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    exit 1
  fi
done

SONAR_BRANCH="${SONAR_BRANCH:-}"
BRANCH_QUERY=""
if [[ -n "$SONAR_BRANCH" ]]; then
  BRANCH_QUERY="&branch=${SONAR_BRANCH}"
fi

quality_gate_json="$(curl -sf -u "${SONAR_TOKEN}:" \
  "${SONAR_HOST_URL}/api/qualitygates/project_status?projectKey=${SONAR_PROJECT_KEY}${BRANCH_QUERY}")"

measures_json="$(curl -sf -u "${SONAR_TOKEN}:" \
  "${SONAR_HOST_URL}/api/measures/component?component=${SONAR_PROJECT_KEY}&metricKeys=security_rating,reliability_rating,sqale_rating,bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density${BRANCH_QUERY}")"

critical_blocker_json="$(curl -sf -u "${SONAR_TOKEN}:" \
  "${SONAR_HOST_URL}/api/issues/search?componentKeys=${SONAR_PROJECT_KEY}&severities=BLOCKER,CRITICAL&resolved=false&ps=1${BRANCH_QUERY}")"

bug_vuln_json="$(curl -sf -u "${SONAR_TOKEN}:" \
  "${SONAR_HOST_URL}/api/issues/search?componentKeys=${SONAR_PROJECT_KEY}&types=BUG,VULNERABILITY&resolved=false&ps=1${BRANCH_QUERY}")"

QUALITY_GATE_JSON="$quality_gate_json" \
MEASURES_JSON="$measures_json" \
CRITICAL_BLOCKER_JSON="$critical_blocker_json" \
BUG_VULN_JSON="$bug_vuln_json" \
python3 - <<'PY'
import json
import os
import sys


def parse_json(env_name: str) -> dict:
    return json.loads(os.environ[env_name])


def is_a(value: str) -> bool:
    normalized = value.strip().upper()
    if normalized == "A":
        return True
    try:
        return float(normalized) <= 1.0
    except ValueError:
        return False


quality_gate_payload = parse_json("QUALITY_GATE_JSON")
measures_payload = parse_json("MEASURES_JSON")
critical_blocker_payload = parse_json("CRITICAL_BLOCKER_JSON")
bug_vuln_payload = parse_json("BUG_VULN_JSON")

quality_gate_status = (
    quality_gate_payload.get("projectStatus", {}).get("status", "UNKNOWN")
)
measures = measures_payload.get("component", {}).get("measures", [])
metrics = {item["metric"]: item.get("value", "") for item in measures}

security_rating = metrics.get("security_rating", "")
reliability_rating = metrics.get("reliability_rating", "")
maintainability_rating = metrics.get("sqale_rating", "")
bugs = int(float(metrics.get("bugs", "0") or "0"))
vulnerabilities = int(float(metrics.get("vulnerabilities", "0") or "0"))
code_smells = int(float(metrics.get("code_smells", "0") or "0"))
coverage = metrics.get("coverage", "N/A")
duplication = metrics.get("duplicated_lines_density", "N/A")

critical_blocker_open = int(critical_blocker_payload.get("total", 0))
bug_vuln_open = int(bug_vuln_payload.get("total", 0))

summary_lines = [
    "### Sonar Policy Report",
    "",
    f"- Quality Gate: `{quality_gate_status}`",
    f"- Security Rating: `{security_rating}`",
    f"- Reliability Rating: `{reliability_rating}`",
    f"- Maintainability Rating: `{maintainability_rating}`",
    f"- Open Bugs (all severities): `{bugs}`",
    f"- Open Vulnerabilities (all severities): `{vulnerabilities}`",
    f"- Open Code Smells: `{code_smells}`",
    f"- Open Critical/Blocker issues: `{critical_blocker_open}`",
    f"- Open BUG/VULNERABILITY issues: `{bug_vuln_open}`",
    f"- Coverage: `{coverage}`",
    f"- Duplicated Lines Density: `{duplication}`",
]

summary = "\n".join(summary_lines)
print(summary)

github_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
if github_summary_path:
    with open(github_summary_path, "a", encoding="utf-8") as fp:
        fp.write(summary + "\n")

errors = []

if quality_gate_status != "OK":
    errors.append(f"Quality Gate status is {quality_gate_status} (expected OK).")

if not is_a(security_rating):
    errors.append(f"Security rating must be A (current: {security_rating}).")

if not is_a(reliability_rating):
    errors.append(f"Reliability rating must be A (current: {reliability_rating}).")

if not is_a(maintainability_rating):
    errors.append(
        f"Maintainability rating must be A (current: {maintainability_rating})."
    )

if critical_blocker_open > 0:
    errors.append(
        f"There are {critical_blocker_open} open critical/blocker issues."
    )

if bugs > 0:
    errors.append(f"There are {bugs} open bugs.")

if vulnerabilities > 0:
    errors.append(f"There are {vulnerabilities} open vulnerabilities.")

if bug_vuln_open > 0:
    errors.append(
        f"There are {bug_vuln_open} open BUG/VULNERABILITY issues in issues API."
    )

if errors:
    print("\nSonar policy check failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    sys.exit(1)

print("\nSonar policy check passed.")
PY
