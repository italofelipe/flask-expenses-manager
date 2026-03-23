from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_python_inline(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_generate_recurring_transactions_script_imports_app_from_repo_root() -> None:
    result = _run_python_inline(
        "import runpy; "
        "runpy.run_path("
        "'scripts/generate_recurring_transactions.py', "
        "run_name='not_main'"
        ")"
    )
    assert result.returncode == 0, result.stderr


def test_manage_audit_events_script_imports_app_from_repo_root() -> None:
    result = _run_python_inline(
        "import runpy; "
        "runpy.run_path("
        "'scripts/manage_audit_events.py', "
        "run_name='not_main'"
        ")"
    )
    assert result.returncode == 0, result.stderr
