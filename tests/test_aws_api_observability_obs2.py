from __future__ import annotations

import json
import subprocess
from typing import Any

from scripts import aws_api_observability_obs2


def test_run_aws_skips_empty_profile(monkeypatch) -> None:
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

    monkeypatch.setattr(aws_api_observability_obs2.subprocess, "run", fake_run)
    ctx = aws_api_observability_obs2.AwsCtx(profile="", region="us-east-1")

    data = aws_api_observability_obs2._run_aws(ctx, ["sts", "get-caller-identity"])

    assert data == {"ok": True}
    assert "--profile" not in captured["cmd"]
    assert "--region" in captured["cmd"]


def test_build_dashboard_body_includes_low_cost_operational_widgets() -> None:
    body = aws_api_observability_obs2.build_dashboard_body(
        region="us-east-1",
        dev_instance_id="i-dev",
        prod_instance_id="i-prod",
        dev_log_group="/auraxis/dev/containers",
        prod_log_group="/auraxis/prod/containers",
    )

    assert body["start"] == "-PT24H"
    widgets = body["widgets"]
    titles = {widget["properties"]["title"] for widget in widgets}
    assert "DEV host baseline (i-dev)" in titles
    assert "PROD host baseline (i-prod)" in titles
    assert "PROD 5xx by route (24h)" in titles
    assert "PROD p95 latency by route (24h)" in titles
    assert "PROD billing webhook invalid signature (24h)" in titles

    prod_5xx = next(
        widget
        for widget in widgets
        if widget["properties"]["title"] == "PROD 5xx by route (24h)"
    )
    assert "SOURCE '/auraxis/prod/containers'" in prod_5xx["properties"]["query"]
    assert "toNumber(status) >= 500" in prod_5xx["properties"]["query"]


def test_invalid_signature_metric_filter_uses_expected_pattern(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_aws(
        ctx: Any, args: list[str], *, expect_json: bool = True
    ) -> dict[str, Any]:
        captured["args"] = args
        return {}

    monkeypatch.setattr(aws_api_observability_obs2, "_run_aws", fake_run_aws)

    aws_api_observability_obs2.ensure_invalid_signature_metric_filter(
        aws_api_observability_obs2.AwsCtx(profile="", region="us-east-1"),
        log_group_name="/auraxis/prod/containers",
        filter_name="auraxis-billing-webhook-invalid-signature-prod",
        namespace="Auraxis/API",
        metric_name="billing_webhook_invalid_signature_prod",
    )

    args = captured["args"]
    assert args[:2] == ["logs", "put-metric-filter"]
    assert '"Billing webhook invalid signature"' in args
    assert "billing_webhook_invalid_signature_prod" in "".join(args)
