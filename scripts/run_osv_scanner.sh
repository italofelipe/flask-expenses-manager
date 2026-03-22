#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${ROOT_DIR}/reports/security"
REPORT_FILE="${REPORT_DIR}/osv-results.json"
OSV_SCANNER_VERSION="${OSV_SCANNER_VERSION:-2.3.3}"
OSV_INCLUDE_NODE_LOCKFILE="${OSV_INCLUDE_NODE_LOCKFILE:-false}"

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
  args=(scan source --recursive)

  if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
    args+=(--lockfile "${ROOT_DIR}/requirements.txt")
  fi

  if [[ "${OSV_INCLUDE_NODE_LOCKFILE}" == "true" && -f "${ROOT_DIR}/package-lock.json" ]]; then
    args+=(--lockfile "${ROOT_DIR}/package-lock.json")
  fi

  args+=(--format json --output "${REPORT_FILE}")
  printf '%s\n' "${args[@]}"
}

main() {
  local scanner_path
  mapfile -t scan_args < <(build_scan_args)
  scanner_path="$(ensure_osv_scanner)"

  echo "[osv-scanner] version=${OSV_SCANNER_VERSION}"
  echo "[osv-scanner] report=${REPORT_FILE}"
  "${scanner_path}" "${scan_args[@]}"
}

main "$@"
