#!/usr/bin/env bash
set -euo pipefail

# Run a local pipeline that mirrors the most important GitHub Actions checks.
#
# Default mode runs in a `python:3.11-slim` container for parity with CI.
# Use `--local` to run using the current Python environment.
#
# This script is meant to be run before pushing changes to avoid CI surprises.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="docker"
if [[ "${1:-}" == "--local" ]]; then
  MODE="local"
fi

run_pipeline() {
  pip-audit -r requirements.txt
  black --check .
  isort --check-only app tests config run.py run_without_db.py
  flake8 app tests config run.py run_without_db.py
  mypy app
  bandit -r app -lll -iii
  pytest -m "not schemathesis" --cov=app --cov-fail-under=85 \
    --cov-report=term-missing --cov-report=xml
  bash scripts/security_evidence_check.sh
}

if [[ "$MODE" == "docker" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for default mode. Use '--local' to run locally." >&2
    exit 1
  fi

  echo "[ci-like-local] Running pipeline in python:3.11-slim container..."
  docker run --rm \
    -v "$ROOT_DIR:/workspace" \
    -w /workspace \
    python:3.11-slim \
    bash -lc "python -m pip install --upgrade pip && \
      pip install -r requirements.txt && \
      pip install -r requirements-dev.txt && \
      run_pipeline() { \
        pip-audit -r requirements.txt && \
        black --check . && \
        isort --check-only app tests config run.py run_without_db.py && \
        flake8 app tests config run.py run_without_db.py && \
        mypy app && \
        bandit -r app -lll -iii && \
        pytest -m \"not schemathesis\" --cov=app --cov-fail-under=85 \
          --cov-report=term-missing --cov-report=xml && \
        bash scripts/security_evidence_check.sh; \
      }; \
      run_pipeline"
  echo "[ci-like-local] All checks passed (Docker / Python 3.11)."
  exit 0
fi

if ! command -v python >/dev/null 2>&1; then
  echo "Python is required for --local mode." >&2
  exit 1
fi

echo "[ci-like-local] Running pipeline in local environment..."
run_pipeline
echo "[ci-like-local] All checks passed (local environment)."

