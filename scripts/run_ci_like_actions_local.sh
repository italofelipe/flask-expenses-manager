#!/usr/bin/env bash
set -euo pipefail

# Run a local gate bundle that mirrors CI checks.
#
# Default: dockerized python:3.11 parity for quality/tests/security-evidence.
# Flags:
#   --local               run in current environment (no docker wrapper)
#   --fast                skip schemathesis checks
#   --with-mutation       include cosmic-ray mutation gate
#   --with-postman        run Postman/Newman smoke suite (expects API at localhost:3333)
#   --help                show usage
#
# Notes:
# - Trivy/Snyk jobs remain CI-native because they depend on runner secrets/tools.
# - Use this script before push to reduce CI surprises.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck source=./lib_python.sh
source "${ROOT_DIR}/scripts/lib_python.sh"

MODE="docker"
RUN_SCHEMATHESIS=1
RUN_MUTATION=0
RUN_POSTMAN=0
PYTHON_BIN=""

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[ci-like-local] missing required command: $cmd" >&2
    return 1
  fi
}

ensure_local_dependencies() {
  PYTHON_BIN="$(resolve_repo_python "$ROOT_DIR")"
  local missing=0
  local required_modules=(pip_audit ruff mypy bandit pytest)
  local module_name

  for module_name in "${required_modules[@]}"; do
    if ! python_has_module "$PYTHON_BIN" "$module_name"; then
      echo "[ci-like-local] missing required Python module: $module_name" >&2
      missing=1
    fi
  done

  if [[ "$missing" -eq 1 ]]; then
    cat >&2 <<'EOF'
[ci-like-local] one or more required Python modules are missing.
Install dev dependencies first:
  bash scripts/bootstrap_local_env.sh
EOF
    exit 3
  fi

  if [[ "$RUN_POSTMAN" -eq 1 ]] && ! require_command newman; then
    echo "[ci-like-local] missing required command: newman" >&2
    echo "[ci-like-local] install with: npm install -g newman" >&2
    exit 3
  fi
}

usage() {
  cat <<'EOF'
Usage: bash scripts/run_ci_like_actions_local.sh [options]

Options:
  --local           Run checks in the current shell environment
  --fast            Skip schemathesis contract checks
  --with-mutation   Include mutation testing gate (cosmic ray)
  --with-postman    Include Postman/Newman smoke suite
  --help            Show this help

Examples:
  bash scripts/run_ci_like_actions_local.sh
  bash scripts/run_ci_like_actions_local.sh --local
  bash scripts/run_ci_like_actions_local.sh --local --with-mutation
  bash scripts/run_ci_like_actions_local.sh --local --with-postman
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      MODE="local"
      shift
      ;;
    --fast)
      RUN_SCHEMATHESIS=0
      shift
      ;;
    --with-mutation)
      RUN_MUTATION=1
      shift
      ;;
    --with-postman)
      RUN_POSTMAN=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

run_core_pipeline() {
  echo "[ci-like-local] step=flags:hygiene"
  "${PYTHON_BIN}" scripts/check_feature_flags.py

  echo "[ci-like-local] step=quality:pip-audit"
  "${PYTHON_BIN}" -m pip_audit -r requirements.txt

  echo "[ci-like-local] step=quality:ruff-format"
  "${PYTHON_BIN}" -m ruff format --check .

  echo "[ci-like-local] step=quality:ruff-check"
  "${PYTHON_BIN}" -m ruff check app tests config run.py run_without_db.py

  echo "[ci-like-local] step=quality:mypy"
  "${PYTHON_BIN}" -m mypy app

  echo "[ci-like-local] step=quality:bandit"
  "${PYTHON_BIN}" -m bandit -r app -lll -iii

  if command -v gitleaks >/dev/null 2>&1; then
    echo "[ci-like-local] step=security:gitleaks"
    gitleaks detect --source . --verbose --redact --config .gitleaks.toml
  else
    echo "[ci-like-local] step=security:gitleaks skipped (gitleaks not installed)"
  fi

  echo "[ci-like-local] step=tests:pytest+coverage"
  "${PYTHON_BIN}" -m pytest -m "not schemathesis" \
    --cov=app \
    --cov-fail-under=85 \
    --cov-report=term-missing \
    --cov-report=xml

  if [[ "$RUN_SCHEMATHESIS" -eq 1 ]]; then
    echo "[ci-like-local] step=tests:schemathesis"
    SCHEMATHESIS_MAX_EXAMPLES="${SCHEMATHESIS_MAX_EXAMPLES:-5}" \
    HYPOTHESIS_SEED="${HYPOTHESIS_SEED:-20260220}" \
      bash scripts/run_schemathesis_contract.sh
  else
    echo "[ci-like-local] step=tests:schemathesis skipped (--fast)"
  fi

  echo "[ci-like-local] step=security:evidence"
  bash scripts/security_evidence_check.sh

  if [[ "$RUN_MUTATION" -eq 1 ]]; then
    echo "[ci-like-local] step=quality:mutation"
    bash scripts/mutation_gate.sh
  else
    echo "[ci-like-local] step=quality:mutation skipped (use --with-mutation)"
  fi

  if [[ "$RUN_POSTMAN" -eq 1 ]]; then
    echo "[ci-like-local] step=tests:postman-smoke"
    bash scripts/run_postman_suite.sh \
      api-tests/postman/environments/local.postman_environment.json
  else
    echo "[ci-like-local] step=tests:postman-smoke skipped (use --with-postman)"
  fi
}

run_in_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for default mode. Use --local to run in current environment." >&2
    exit 1
  fi

  local docker_args=()
  if [[ "$RUN_SCHEMATHESIS" -eq 0 ]]; then
    docker_args+=("--fast")
  fi
  if [[ "$RUN_MUTATION" -eq 1 ]]; then
    docker_args+=("--with-mutation")
  fi
  if [[ "$RUN_POSTMAN" -eq 1 ]]; then
    echo "[ci-like-local] --with-postman is supported only in --local mode." >&2
    echo "[ci-like-local] Start stack and rerun with --local --with-postman." >&2
    exit 4
  fi

  echo "[ci-like-local] Running in python:3.11-slim container..."
  docker run --rm \
    -v "$ROOT_DIR:/workspace" \
    -w /workspace \
    python:3.11-slim \
    bash -lc "python -m pip install --upgrade pip && \
      pip install -r requirements.txt && \
      pip install -r requirements-dev.txt && \
      bash scripts/run_ci_like_actions_local.sh --local ${docker_args[*]}"

  echo "[ci-like-local] All selected checks passed (docker mode)."
}

run_in_local() {
  ensure_local_dependencies

  echo "[ci-like-local] Running in local environment with ${PYTHON_BIN}..."
  run_core_pipeline
  echo "[ci-like-local] All selected checks passed (local mode)."
}

if [[ "$MODE" == "docker" ]]; then
  run_in_docker
else
  run_in_local
fi
