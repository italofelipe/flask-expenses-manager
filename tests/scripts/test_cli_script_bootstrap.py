from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import scripts.generate_recurring_transactions as recurrence_script

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


def test_generate_recurring_transactions_uses_internal_runtime(
    monkeypatch,
) -> None:
    called: dict[str, object] = {}

    class _AppContext:
        def __enter__(self) -> "_AppContext":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakeApp:
        def app_context(self) -> _AppContext:
            return _AppContext()

    def _fake_create_app(*, enable_http_runtime: bool = True) -> _FakeApp:
        called["enable_http_runtime"] = enable_http_runtime
        return _FakeApp()

    monkeypatch.setattr(recurrence_script, "create_app", _fake_create_app)
    monkeypatch.setattr(
        recurrence_script,
        "RecurrenceService",
        SimpleNamespace(generate_missing_occurrences=lambda reference_date: 0),
    )

    exit_code = recurrence_script.main()

    assert called == {"enable_http_runtime": False}
    assert exit_code == 0


def test_generate_recurring_transactions_returns_1_on_service_error(
    monkeypatch,
) -> None:
    class _AppContext:
        def __enter__(self) -> "_AppContext":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakeApp:
        def app_context(self) -> _AppContext:
            return _AppContext()

    monkeypatch.setattr(
        recurrence_script,
        "create_app",
        lambda *, enable_http_runtime=True: _FakeApp(),
    )

    def _failing_service(*, reference_date):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(
        recurrence_script,
        "RecurrenceService",
        SimpleNamespace(generate_missing_occurrences=_failing_service),
    )

    exit_code = recurrence_script.main()

    assert exit_code == 1


def test_generate_recurring_transactions_returns_1_on_factory_error(
    monkeypatch,
) -> None:
    def _bad_factory(*, enable_http_runtime=True):
        raise RuntimeError("factory boom")

    monkeypatch.setattr(recurrence_script, "create_app", _bad_factory)

    exit_code = recurrence_script.main()

    assert exit_code == 1
