from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from scripts import aws_iam_audit_i8


def test_finding_level_detection() -> None:
    assert aws_iam_audit_i8._finding_level("FAIL: missing action") == "fail"
    assert aws_iam_audit_i8._finding_level("WARN: broad policy") == "warn"
    assert aws_iam_audit_i8._finding_level("PASS: ok") == "pass"
    assert aws_iam_audit_i8._finding_level("unexpected text") == "pass"


def test_build_summary_aggregates_all_sections() -> None:
    report: dict[str, Any] = {
        "dev": {"findings": ["PASS: dev ok", "WARN: dev warning"]},
        "prod": {"findings": ["FAIL: prod failure"]},
        "deploy_roles": {
            "dev": {"findings": ["WARN: trust subject missing"]},
            "prod": {"findings": ["PASS: role ok"]},
        },
    }
    summary = aws_iam_audit_i8._build_summary(report)
    assert summary == {"pass": 2, "warn": 2, "fail": 1}


@pytest.mark.parametrize(
    ("summary", "fail_on", "expected"),
    [
        ({"pass": 2, "warn": 0, "fail": 0}, "none", False),
        ({"pass": 2, "warn": 1, "fail": 0}, "none", False),
        ({"pass": 2, "warn": 1, "fail": 0}, "warn", True),
        ({"pass": 2, "warn": 0, "fail": 1}, "warn", True),
        ({"pass": 2, "warn": 1, "fail": 0}, "fail", False),
        ({"pass": 2, "warn": 0, "fail": 1}, "fail", True),
    ],
)
def test_should_fail_thresholds(
    summary: dict[str, int], fail_on: str, expected: bool
) -> None:
    assert aws_iam_audit_i8._should_fail(summary, fail_on) is expected


def test_run_aws_skips_empty_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(
        cmd: list[str], capture_output: bool, text: bool, check: bool
    ) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    monkeypatch.setattr(aws_iam_audit_i8.subprocess, "run", fake_run)
    ctx = aws_iam_audit_i8.AwsCtx(profile="", region="us-east-1")
    data = aws_iam_audit_i8._run_aws(ctx, ["sts", "get-caller-identity"])

    assert data == {"ok": True}
    assert "--profile" not in captured["cmd"]
    assert "--region" in captured["cmd"]
