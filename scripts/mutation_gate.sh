#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi

MUTATION_CONFIG_FILE="${MUTATION_CONFIG_FILE:-scripts/cosmic_ray.toml}"
MUTATION_MAX_SURVIVAL_PERCENT="${MUTATION_MAX_SURVIVAL_PERCENT:-0.0}"

if [[ ! -f "${MUTATION_CONFIG_FILE}" ]]; then
  echo "Mutation config file not found: ${MUTATION_CONFIG_FILE}" >&2
  exit 1
fi

SESSION_FILE="${TMPDIR:-/tmp}/auraxis-cosmic-ray-$(date +%s)-$$.sqlite"

echo "Running mutation baseline (Cosmic Ray)..."
"${PYTHON_BIN}" -m cosmic_ray.cli baseline "${MUTATION_CONFIG_FILE}"

echo "Initializing mutation session..."
"${PYTHON_BIN}" -m cosmic_ray.cli init "${MUTATION_CONFIG_FILE}" "${SESSION_FILE}"

echo "Applying operator filters..."
"${PYTHON_BIN}" -m cosmic_ray.tools.filters.operators_filter \
  "${SESSION_FILE}" \
  "${MUTATION_CONFIG_FILE}"

echo "Executing mutation tests..."
"${PYTHON_BIN}" -m cosmic_ray.cli exec "${MUTATION_CONFIG_FILE}" "${SESSION_FILE}"

echo "Mutation summary:"
"${PYTHON_BIN}" -m cosmic_ray.tools.report "${SESSION_FILE}"

echo "Enforcing mutation survival threshold <= ${MUTATION_MAX_SURVIVAL_PERCENT}%..."
"${PYTHON_BIN}" -m cosmic_ray.tools.survival_rate \
  "${SESSION_FILE}" \
  --fail-over "${MUTATION_MAX_SURVIVAL_PERCENT}"

echo "Mutation gate passed."
