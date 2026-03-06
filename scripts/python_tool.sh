#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./lib_python.sh
source "${ROOT_DIR}/scripts/lib_python.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/python_tool.sh <module> [args...]" >&2
  exit 2
fi

PYTHON_BIN="$(resolve_repo_python "$ROOT_DIR")"
exec "$PYTHON_BIN" -m "$@"
