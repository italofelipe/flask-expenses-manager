from __future__ import annotations

import subprocess
import sys
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


def test_resolve_repo_python_uses_pyenv_fallback_when_path_lacks_python_313(
    tmp_path: Path,
) -> None:
    pyenv_root = tmp_path / "pyenv-root"
    pyenv_bin_dir = tmp_path / "bin"
    fake_python_dir = pyenv_root / "versions" / "3.13.99" / "bin"
    fake_pyenv = pyenv_bin_dir / "pyenv"

    fake_python_dir.mkdir(parents=True)
    pyenv_bin_dir.mkdir(parents=True)

    (fake_python_dir / "python").symlink_to(Path(sys.executable))
    fake_pyenv.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail

case "${{1:-}}" in
  versions)
    printf '3.13.99\\n'
    ;;
  prefix)
    printf '%s\\n' "{pyenv_root / "versions" / "3.13.99"}"
    ;;
  *)
    exit 1
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_pyenv.chmod(0o755)

    script = f"""
      set -euo pipefail
      source "{LIB_PYTHON}"
      unset PYTHON_BIN
      unset VIRTUAL_ENV
      export VENV_DIR="{ROOT}/.venv-missing-for-test"
      export PATH="{pyenv_bin_dir}:/usr/bin:/bin"
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
