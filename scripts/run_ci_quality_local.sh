#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="docker"
if [[ "${1:-}" == "--local" ]]; then
  MODE="local"
fi

PYTHON_FILES_LIST="$(mktemp)"
trap 'rm -f "$PYTHON_FILES_LIST"' EXIT
git ls-files "*.py" >"$PYTHON_FILES_LIST"

if [[ "$MODE" == "docker" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for default mode. Use '--local' to run with current environment." >&2
    exit 1
  fi

  echo "[quality-local] Running CI quality pipeline in python:3.11-slim container..."
  docker run --rm \
    -v "$ROOT_DIR:/workspace" \
    -v "$PYTHON_FILES_LIST:/tmp/python_files.txt:ro" \
    -w /workspace \
    python:3.11-slim \
    bash -lc "python -m pip install --upgrade pip && \
      pip install -r requirements.txt && \
      pip install -r requirements-dev.txt && \
      pip install pip-audit bandit && \
      pip-audit -r requirements.txt && \
      black --check \$(tr '\n' ' ' </tmp/python_files.txt) && \
      isort --check-only app tests config run.py run_without_db.py && \
      flake8 app tests config run.py run_without_db.py && \
      mypy app && \
      bandit -r app -lll -iii"
  echo "[quality-local] All quality checks passed (Docker / Python 3.11)."
  exit 0
fi

if ! command -v python >/dev/null 2>&1; then
  echo "Python is required for --local mode." >&2
  exit 1
fi

echo "[quality-local] Running CI quality pipeline in local environment..."
pip-audit -r requirements.txt
black --check $(tr '\n' ' ' <"$PYTHON_FILES_LIST")
isort --check-only app tests config run.py run_without_db.py
flake8 app tests config run.py run_without_db.py
mypy app
bandit -r app -lll -iii
echo "[quality-local] All quality checks passed (local environment)."
