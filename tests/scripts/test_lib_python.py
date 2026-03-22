from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB_PYTHON = ROOT / "scripts" / "lib_python.sh"


def _run_shell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_resolve_repo_python_uses_pyenv_fallback_when_path_lacks_python_313() -> None:
    script = f"""
      set -euo pipefail
      source "{LIB_PYTHON}"
      unset PYTHON_BIN
      unset VIRTUAL_ENV
      export VENV_DIR="{ROOT}/.venv-missing-for-test"
      export PYENV_BIN="/opt/homebrew/bin/pyenv"
      export PATH="/usr/bin:/bin"
      python_bin="$(resolve_repo_python "{ROOT}")"
      "$python_bin" - <<'PY'
import sys
assert sys.version_info[:2] == (3, 13)
PY
      printf '%s\\n' "$python_bin"
    """
    result = _run_shell(script)
    assert result.returncode == 0, result.stderr
    assert "/versions/3.13" in result.stdout
