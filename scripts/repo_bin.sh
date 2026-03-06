#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./lib_python.sh
source "${ROOT_DIR}/scripts/lib_python.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/repo_bin.sh <tool> [args...]" >&2
  exit 2
fi

TOOL_NAME="$1"
shift

TOOL_BIN="$(resolve_repo_bin "$TOOL_NAME" "$ROOT_DIR")"
exec "$TOOL_BIN" "$@"
