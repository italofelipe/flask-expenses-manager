#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck source=./lib_python.sh
source "${ROOT_DIR}/scripts/lib_python.sh"

MODE="docker"
if [[ "${1:-}" == "--local" ]]; then
  MODE="local"
fi

if [[ "$MODE" == "docker" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for default mode. Use '--local' to run with current environment." >&2
    exit 1
  fi

  echo "[quality-local] Running CI quality pipeline in python:3.13-slim container..."
  docker run --rm \
    -v "$ROOT_DIR:/workspace" \
    -w /workspace \
    python:3.13-slim \
    bash -lc "python -m pip install --upgrade pip && \
      python -m pip install -r requirements.txt -r requirements-dev.txt && \
      python -m pip_audit -r requirements.txt && \
      python -m ruff format --check . && \
      python -m ruff check app tests config run.py run_without_db.py && \
      python -m mypy app && \
      python -m bandit -r app -lll -iii"
  echo "[quality-local] All quality checks passed (Docker / Python 3.13)."
  exit 0
fi

PYTHON_BIN="$(resolve_repo_python "$ROOT_DIR")"

echo "[quality-local] Running CI quality pipeline in local environment with ${PYTHON_BIN}..."
"${PYTHON_BIN}" -m pip_audit -r requirements.txt
"${PYTHON_BIN}" -m ruff format --check .
"${PYTHON_BIN}" -m ruff check app tests config run.py run_without_db.py
"${PYTHON_BIN}" -m mypy app
"${PYTHON_BIN}" -m bandit -r app -lll -iii
echo "[quality-local] All quality checks passed (local environment)."
