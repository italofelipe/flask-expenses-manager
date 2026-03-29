from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "ci_stack_bootstrap.py"
    )
    spec = importlib.util.spec_from_file_location("ci_stack_bootstrap", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bootstrap_stack_records_successful_bootstrap(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    calls: list[list[str]] = []

    class Result:
        def __init__(
            self, returncode: int = 0, stdout: str = "", stderr: str = ""
        ) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(args, check=False):
        calls.append(args)
        return Result()

    monkeypatch.setattr(module, "_run_subprocess", fake_run)
    monkeypatch.setattr(module, "_check_health", lambda *args, **kwargs: None)

    config = module.BootstrapConfig(
        compose_file="docker-compose.ci.yml",
        reports_dir=tmp_path,
        health_url="http://localhost:3333/healthz",
        migration_command="flask db upgrade",
        services=("db", "redis", "web"),
        up_attempts=2,
        migration_attempts=2,
        health_attempts=2,
        retry_sleep_seconds=1,
        health_timeout_seconds=1,
    )

    report = module._bootstrap_stack(config, sleep_fn=lambda *_: None)

    assert report.status == "ok"
    assert report.failed_phase is None
    assert [record.phase for record in report.attempts] == [
        "boot",
        "migration",
        "health",
    ]
    assert calls[0] == [
        "docker",
        "compose",
        "-f",
        "docker-compose.ci.yml",
        "up",
        "-d",
        "db",
        "redis",
        "web",
    ]


def test_bootstrap_stack_dumps_diagnostics_when_boot_fails(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()

    class Result:
        def __init__(
            self, returncode: int = 0, stdout: str = "", stderr: str = ""
        ) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(args, check=False):
        if args[:6] == [
            "docker",
            "compose",
            "-f",
            "docker-compose.ci.yml",
            "up",
            "-d",
        ]:
            return Result(returncode=1, stderr="boot failed")
        if "ps" in args:
            return Result(stdout="ps output")
        if "logs" in args:
            return Result(stdout="logs output")
        return Result()

    monkeypatch.setattr(module, "_run_subprocess", fake_run)

    config = module.BootstrapConfig(
        compose_file="docker-compose.ci.yml",
        reports_dir=tmp_path,
        health_url="http://localhost:3333/healthz",
        migration_command="flask db upgrade",
        services=("db", "redis", "web"),
        up_attempts=1,
        migration_attempts=1,
        health_attempts=1,
        retry_sleep_seconds=1,
        health_timeout_seconds=1,
    )

    report = module._bootstrap_stack(config, sleep_fn=lambda *_: None)

    assert report.status == "failed"
    assert report.failed_phase == "boot"
    assert report.diagnostics
    ps_path = Path(report.diagnostics[0].ps_path)
    logs_path = Path(report.diagnostics[0].logs_path)
    assert ps_path.read_text(encoding="utf-8") == "ps output"
    assert logs_path.read_text(encoding="utf-8") == "logs output"


def test_main_bootstrap_writes_report_file(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    report_path = tmp_path / "bootstrap-report.json"

    monkeypatch.setattr(
        module,
        "_bootstrap_stack",
        lambda config: module.BootstrapReport(status="ok", failed_phase=None),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_stack_bootstrap.py",
            "bootstrap",
            "--report-path",
            str(report_path),
            "--reports-dir",
            str(tmp_path / "diagnostics"),
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
