from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ci_suite_canary.py"
    spec = importlib.util.spec_from_file_location("ci_suite_canary", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_flags_marks_exceeded_thresholds() -> None:
    module = _load_module()
    flags = module._build_flags(
        total_duration_ms=800000,
        bootstrap_duration_ms=250000,
        smoke_duration_ms=190000,
        max_total_duration_ms=720000,
        max_bootstrap_duration_ms=240000,
        max_smoke_duration_ms=180000,
    )

    assert flags == [
        "total_duration_budget_exceeded",
        "bootstrap_duration_budget_exceeded",
        "smoke_duration_budget_exceeded",
    ]


def test_main_writes_report_for_successful_canary(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_DB=test\n", encoding="utf-8")
    report_dir = tmp_path / "reports"

    def fake_run_named_phase(*, phase_name, args, env=None):
        return module.PhaseResult(
            name=phase_name,
            success=True,
            duration_ms=100,
            command=" ".join(args),
            detail="ok",
        )

    monkeypatch.setattr(module, "_run_named_phase", fake_run_named_phase)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_suite_canary.py",
            "--compose-file",
            "docker-compose.ci.yml",
            "--env-file",
            str(env_file),
            "--report-dir",
            str(report_dir),
            "--web-image",
            "auraxis-ci-dev:test",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    payload = json.loads(
        (report_dir / "suite-canary-report.json").read_text(encoding="utf-8")
    )
    assert payload["status"] == "ok"
    assert payload["redundant_rebuilds"] == 0
    assert payload["estimated_runner_cost_usd"] >= 0


def test_main_fails_when_sustainability_budget_is_exceeded(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_DB=test\n", encoding="utf-8")
    report_dir = tmp_path / "reports"

    def fake_run_named_phase(*, phase_name, args, env=None):
        duration_ms = 500000 if phase_name == "stack_bootstrap" else 100
        return module.PhaseResult(
            name=phase_name,
            success=True,
            duration_ms=duration_ms,
            command=" ".join(args),
            detail="ok",
        )

    monkeypatch.setattr(module, "_run_named_phase", fake_run_named_phase)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_suite_canary.py",
            "--compose-file",
            "docker-compose.ci.yml",
            "--env-file",
            str(env_file),
            "--report-dir",
            str(report_dir),
            "--web-image",
            "auraxis-ci-dev:test",
            "--max-bootstrap-duration-ms",
            "1000",
        ],
    )

    exit_code = module.main()

    assert exit_code == 1
    payload = json.loads(
        (report_dir / "suite-canary-report.json").read_text(encoding="utf-8")
    )
    assert "bootstrap_duration_budget_exceeded" in payload["sustainability_flags"]
