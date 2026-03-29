from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "ci_failure_summary.py"
    )
    spec = importlib.util.spec_from_file_location("ci_failure_summary", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_classifies_bootstrap_health_failure(tmp_path: Path) -> None:
    module = _load_module()
    bootstrap_path = tmp_path / "bootstrap-report.json"
    bootstrap_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "failed_phase": "health",
                "total_duration_ms": 1450,
                "attempts": [
                    {
                        "phase": "boot",
                        "attempt": 1,
                        "success": True,
                        "detail": "ok",
                        "duration_ms": 120,
                    },
                    {
                        "phase": "migration",
                        "attempt": 1,
                        "success": True,
                        "detail": "ok",
                        "duration_ms": 430,
                    },
                ],
                "diagnostics": [{"ps_path": "ps.txt", "logs_path": "logs.txt"}],
            }
        ),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    report = module.SummaryReport(
        job_name="API Smoke",
        profile="smoke",
        job_status="failure",
        category=module._classify_failure(
            job_status="failure",
            step_outcomes={"bootstrap": "failure"},
            bootstrap=module._load_bootstrap(bootstrap_path),
            newman=None,
            latency=None,
        ),
        step_outcomes={"bootstrap": "failure"},
        bootstrap=module._load_bootstrap(bootstrap_path),
        newman=None,
        latency=None,
        artifacts=[],
    )

    assert report.category.code == "infra.stack_readiness"
    assert report.bootstrap is not None
    assert report.bootstrap.total_duration_ms == 1450


def test_classifies_newman_assertion_failure(tmp_path: Path) -> None:
    module = _load_module()
    report_path = tmp_path / "newman.xml"
    report_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="newman" tests="3" failures="1">
    <testcase classname="smoke" name="login happy path" />
    <testcase classname="smoke" name="graphql invalid login">
      <failure message="expected status 200">AssertionError</failure>
    </testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )

    newman = module._load_newman(report_path)
    assert newman is not None
    assert newman.failures == 1
    assert newman.first_failure_name == "graphql invalid login"

    category = module._classify_failure(
        job_status="failure",
        step_outcomes={"newman": "failure"},
        bootstrap=None,
        newman=newman,
        latency=None,
    )

    assert category.code == "contract.postman_assertion"


def test_writes_summary_and_json_report(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    bootstrap_path = reports_dir / "bootstrap-report.json"
    bootstrap_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "failed_phase": None,
                "total_duration_ms": 900,
                "attempts": [],
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    latency_path = reports_dir / "latency.json"
    latency_path.write_text(
        json.dumps(
            {
                "all_within_budget": False,
                "routes": {
                    "user.me": {"within_budget": True},
                    "graphql.me": {"within_budget": False},
                },
            }
        ),
        encoding="utf-8",
    )
    step_summary = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_failure_summary.py",
            "--job-name",
            "API Smoke",
            "--profile",
            "smoke",
            "--job-status",
            "failure",
            "--reports-dir",
            str(reports_dir),
            "--bootstrap-report",
            str(bootstrap_path),
            "--latency-report",
            str(latency_path),
            "--step-outcome",
            "latency=failure",
            "--write-summary",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    summary_path = reports_dir / "diagnostic-summary.md"
    json_path = reports_dir / "diagnostic-summary.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["category"]["code"] == "performance.latency_budget"
    assert "graphql.me" in payload["latency"]["offenders"]
    assert "performance.latency_budget" in step_summary.read_text(encoding="utf-8")
    assert summary_path.exists()
    assert os.path.exists(json_path)
