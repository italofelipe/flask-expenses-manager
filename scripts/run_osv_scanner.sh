#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${ROOT_DIR}/reports/security"
REPORT_FILE="${REPORT_DIR}/osv-results.json"
OSV_SCANNER_VERSION="${OSV_SCANNER_VERSION:-2.3.3}"
OSV_INCLUDE_NODE_LOCKFILE="${OSV_INCLUDE_NODE_LOCKFILE:-false}"
OSV_ALLOWLIST_VULNS="${OSV_ALLOWLIST_VULNS:-GHSA-5239-wwwm-4pmq}"

mkdir -p "${REPORT_DIR}"

resolve_platform() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"

  case "${os}" in
    linux|darwin) ;;
    *)
      echo "[osv-scanner] unsupported OS: ${os}" >&2
      return 1
      ;;
  esac

  case "${arch}" in
    x86_64|amd64)
      arch="amd64"
      ;;
    arm64|aarch64)
      arch="arm64"
      ;;
    *)
      echo "[osv-scanner] unsupported architecture: ${arch}" >&2
      return 1
      ;;
  esac

  printf '%s_%s\n' "${os}" "${arch}"
}

ensure_osv_scanner() {
  local platform cache_dir binary_path asset_url
  platform="$(resolve_platform)"
  cache_dir="${ROOT_DIR}/.cache/tools/osv-scanner/${OSV_SCANNER_VERSION}"
  binary_path="${cache_dir}/osv-scanner"

  if [[ -x "${binary_path}" ]]; then
    printf '%s\n' "${binary_path}"
    return 0
  fi

  mkdir -p "${cache_dir}"
  asset_url="https://github.com/google/osv-scanner/releases/download/v${OSV_SCANNER_VERSION}/osv-scanner_${platform}"
  curl -fsSL "${asset_url}" -o "${binary_path}"
  chmod +x "${binary_path}"
  printf '%s\n' "${binary_path}"
}

build_scan_args() {
  local -a args
  args=(scan --experimental-no-default-plugins --experimental-plugins lockfile)

  if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
    args+=(--lockfile "${ROOT_DIR}/requirements.txt")
  fi

  if [[ "${OSV_INCLUDE_NODE_LOCKFILE}" == "true" && -f "${ROOT_DIR}/package-lock.json" ]]; then
    args+=(--lockfile "${ROOT_DIR}/package-lock.json")
  fi

  args+=(--format json --output "${REPORT_FILE}")
  printf '%s\n' "${args[@]}"
}

report_has_non_allowlisted_vulns() {
  python3 - "$REPORT_FILE" "$OSV_ALLOWLIST_VULNS" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
allowlist = {item.strip() for item in sys.argv[2].split(",") if item.strip()}

if not report_path.exists():
    print("[osv-scanner] report missing after scan", file=sys.stderr)
    sys.exit(2)

data = json.loads(report_path.read_text())
unexpected = set()

for result in data.get("results", []):
    for package in result.get("packages", []):
        for vuln in package.get("vulnerabilities", []):
            vuln_id = vuln.get("id")
            aliases = set(vuln.get("aliases", []))
            if vuln_id and vuln_id not in allowlist and not aliases.intersection(allowlist):
                unexpected.add(vuln_id)

if unexpected:
    print("[osv-scanner] non-allowlisted vulnerabilities detected:", file=sys.stderr)
    for vuln_id in sorted(unexpected):
      print(f"  - {vuln_id}", file=sys.stderr)
    sys.exit(1)

sys.exit(0)
PY
}

stderr_has_unexpected_lines() {
  local stderr_file
  stderr_file="$1"

  python3 - "$stderr_file" <<'PY'
import sys
from pathlib import Path

stderr_path = Path(sys.argv[1])
known_metadata_files = {
    "flask-apispec-0.11.4.tar.gz",
    "graphql-relay-3.2.0.tar.gz",
}

if not stderr_path.exists():
    sys.exit(1)

unexpected = []
for raw_line in stderr_path.read_text().splitlines():
    line = raw_line.strip()
    if not line:
        continue
    if (
        line.startswith("Starting filesystem walk for root:")
        or line.startswith("Scanned ")
        or line.startswith("End status:")
    ):
        continue
    if line.startswith("failed to parse metadata for file "):
        if any(name in line for name in known_metadata_files):
            continue
    unexpected.append(line)

if unexpected:
    print("[osv-scanner] unexpected stderr detected:", file=sys.stderr)
    for line in unexpected:
        print(f"  - {line}", file=sys.stderr)
    sys.exit(0)

sys.exit(1)
PY
}

main() {
  local scanner_path scan_exit scan_stderr
  mapfile -t scan_args < <(build_scan_args)
  scanner_path="$(ensure_osv_scanner)"
  scan_stderr="$(mktemp)"

  echo "[osv-scanner] version=${OSV_SCANNER_VERSION}"
  echo "[osv-scanner] report=${REPORT_FILE}"

  set +e
  "${scanner_path}" "${scan_args[@]}" 2> >(tee "${scan_stderr}" >&2)
  scan_exit=$?
  set -e

  if ! report_has_non_allowlisted_vulns; then
    rm -f "${scan_stderr}"
    return 1
  fi

  if [[ "${scan_exit}" -ne 0 ]]; then
    if stderr_has_unexpected_lines "${scan_stderr}"; then
      rm -f "${scan_stderr}"
      return 1
    fi
    echo "[osv-scanner] ignoring known metadata parse warnings after successful allowlist evaluation"
  fi

  rm -f "${scan_stderr}"
}

main "$@"
