#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
# shellcheck source=./lib_python.sh
source "${ROOT_DIR}/scripts/lib_python.sh"

resolve_bootstrap_python() {
  local candidate
  for candidate in \
    "${BOOTSTRAP_PYTHON:-${AURAXIS_BOOTSTRAP_PYTHON:-python3.13}}" \
    python3.13 \
    python3.11 \
    python3 \
    python; do
    [[ -z "$candidate" ]] && continue
    if command -v "$candidate" >/dev/null 2>&1; then
      candidate="$(command -v "$candidate")"
      if is_supported_python "$candidate"; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done

  echo "Python interpreter not found. Expected Python 3.11 or 3.13 in PATH." >&2
  exit 1
}

BOOTSTRAP_PYTHON_BIN="$(resolve_bootstrap_python)"

if [[ -x "${VENV_DIR}/bin/python" ]] && ! is_supported_python "${VENV_DIR}/bin/python"; then
  echo "Recreating ${VENV_DIR} because it uses unsupported Python $(python_minor_version "${VENV_DIR}/bin/python")."
  rm -rf "${VENV_DIR}"
fi

if [ ! -d "${VENV_DIR}" ]; then
  echo "Creating virtual environment at ${VENV_DIR}"
  "${BOOTSTRAP_PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

PYTHON_BIN="$(resolve_repo_python "$ROOT_DIR")"
echo "Installing dependencies with ${PYTHON_BIN}"
"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install -r "${ROOT_DIR}/requirements.txt" -r "${ROOT_DIR}/requirements-dev.txt"

echo "Installing pre-commit hooks"
"${PYTHON_BIN}" -m pre_commit install
"${PYTHON_BIN}" -m pre_commit install --hook-type pre-push

echo
echo "Bootstrap completed."
echo "Activate with: source ${VENV_DIR}/bin/activate"
