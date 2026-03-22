from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import aws_deploy_i6


def test_extract_invocation_report_truncates_and_maps_fields() -> None:
    invocation = {
        "Status": "Failed",
        "StatusDetails": "ExecutionTimedOut",
        "ResponseCode": 124,
        "ExecutionStartDateTime": "2026-03-22T10:00:00Z",
        "ExecutionEndDateTime": "2026-03-22T10:05:00Z",
        "StandardOutputUrl": "stdout-url",
        "StandardErrorUrl": "stderr-url",
        "StandardOutputContent": "A" * 15,
        "StandardErrorContent": "B" * 15,
    }

    report = aws_deploy_i6._extract_invocation_report(
        invocation,
        instance_id="i-dev",
        command_id="cmd-123",
    )

    assert report["instance_id"] == "i-dev"
    assert report["command_id"] == "cmd-123"
    assert report["status"] == "Failed"
    assert report["status_details"] == "ExecutionTimedOut"
    assert report["response_code"] == 124
    assert report["stdout_tail"] == "A" * 15
    assert report["stderr_tail"] == "B" * 15


def test_wait_raises_ssm_command_failed_with_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_aws(
        ctx: Any, args: list[str], *, expect_json: bool = True
    ) -> dict[str, Any]:
        return {
            "Status": "Failed",
            "StatusDetails": "ExecutionTimedOut",
            "ResponseCode": 1,
            "StandardOutputContent": "deploy stdout",
            "StandardErrorContent": "deploy stderr",
        }

    monkeypatch.setattr(aws_deploy_i6, "_run_aws", fake_run_aws)
    ctx = aws_deploy_i6.AwsCtx(profile="", region="us-east-1")

    with pytest.raises(aws_deploy_i6.SsmCommandFailed) as exc_info:
        aws_deploy_i6._wait(ctx, command_id="cmd-123", instance_id="i-dev")

    report = exc_info.value.report
    assert report["command_id"] == "cmd-123"
    assert report["instance_id"] == "i-dev"
    assert report["status"] == "Failed"
    assert "deploy stderr" in report["stderr_tail"]


def test_write_diagnostics_json_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "report.json"
    payload = {"status": "Success", "command_id": "cmd-123"}

    aws_deploy_i6._write_diagnostics_json(str(target), payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload


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

    monkeypatch.setattr(aws_deploy_i6.subprocess, "run", fake_run)
    ctx = aws_deploy_i6.AwsCtx(profile="", region="us-east-1")

    data = aws_deploy_i6._run_aws(ctx, ["sts", "get-caller-identity"])

    assert data == {"ok": True}
    assert "--profile" not in captured["cmd"]
    assert "--region" in captured["cmd"]
