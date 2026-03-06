#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./lib_python.sh
source "${ROOT_DIR}/scripts/lib_python.sh"

PYTHON_BIN="$(resolve_repo_python "$ROOT_DIR")"
exec "$PYTHON_BIN" "$@"
