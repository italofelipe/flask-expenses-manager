#!/usr/bin/env bash

python_minor_version() {
  local python_bin="${1:?python_bin is required}"

  "$python_bin" - <<'PY'
import sys

print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
}

is_supported_python() {
  local python_bin="${1:?python_bin is required}"
  local version

  version="$(python_minor_version "$python_bin")"
  [[ "$version" == "3.11" || "$version" == "3.13" ]]
}

resolve_repo_python() {
  local root_dir="${1:?root_dir is required}"
  local configured="${PYTHON_BIN:-}"
  local venv_dir="${VENV_DIR:-${root_dir}/.venv}"
  local candidate

  if [[ -n "$configured" ]]; then
    if [[ -x "$configured" ]]; then
      if is_supported_python "$configured"; then
        printf '%s\n' "$configured"
        return 0
      fi
      echo "Configured PYTHON_BIN uses unsupported Python: $(python_minor_version "$configured"). Expected 3.11 or 3.13." >&2
      return 1
    fi
    if command -v "$configured" >/dev/null 2>&1; then
      candidate="$(command -v "$configured")"
      if is_supported_python "$candidate"; then
        printf '%s\n' "$candidate"
        return 0
      fi
      echo "Configured PYTHON_BIN resolves to unsupported Python: $(python_minor_version "$candidate"). Expected 3.11 or 3.13." >&2
      return 1
    fi
    echo "Configured PYTHON_BIN not found: $configured" >&2
    return 1
  fi

  if [[ -x "${venv_dir}/bin/python" ]]; then
    if is_supported_python "${venv_dir}/bin/python"; then
      printf '%s\n' "${venv_dir}/bin/python"
      return 0
    fi
    echo "Unsupported Python in ${venv_dir}: $(python_minor_version "${venv_dir}/bin/python"). Re-run bash scripts/bootstrap_local_env.sh." >&2
    return 1
  fi

  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    if is_supported_python "${VIRTUAL_ENV}/bin/python"; then
      printf '%s\n' "${VIRTUAL_ENV}/bin/python"
      return 0
    fi
    echo "Unsupported Python in VIRTUAL_ENV (${VIRTUAL_ENV}): $(python_minor_version "${VIRTUAL_ENV}/bin/python"). Expected 3.11 or 3.13." >&2
    return 1
  fi

  for candidate in "${AURAXIS_BOOTSTRAP_PYTHON:-python3.13}" python3.13 python3.11 python3 python; do
    [[ -z "$candidate" ]] && continue
    if command -v "$candidate" >/dev/null 2>&1; then
      candidate="$(command -v "$candidate")"
      if is_supported_python "$candidate"; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done

  echo "No supported Python interpreter found. Expected Python 3.11 or 3.13 in PATH." >&2
  return 1
}

resolve_repo_bin() {
  local tool_name="${1:?tool_name is required}"
  local root_dir="${2:?root_dir is required}"
  local python_bin
  local python_dir

  python_bin="$(resolve_repo_python "$root_dir")" || return 1
  python_dir="$(dirname "$python_bin")"

  if [[ -x "${python_dir}/${tool_name}" ]]; then
    printf '%s\n' "${python_dir}/${tool_name}"
    return 0
  fi

  if command -v "$tool_name" >/dev/null 2>&1; then
    command -v "$tool_name"
    return 0
  fi

  echo "Tool not found: ${tool_name}. Run bash scripts/bootstrap_local_env.sh first." >&2
  return 1
}

python_has_module() {
  local python_bin="${1:?python_bin is required}"
  local module_name="${2:?module_name is required}"

  "$python_bin" - "$module_name" <<'PY'
import importlib.util
import sys

module_name = sys.argv[1]
sys.exit(0 if importlib.util.find_spec(module_name) else 1)
PY
}
