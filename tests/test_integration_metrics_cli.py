from __future__ import annotations

import json

from app.extensions.integration_metrics import increment_metric, reset_metrics_for_tests


def test_integration_metrics_snapshot_filters_by_prefix(app) -> None:
    reset_metrics_for_tests()
    increment_metric("brapi.timeout")
    increment_metric("rate_limit.blocked")

    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["integration-metrics", "snapshot", "--prefix", "brapi."]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["prefix"] == "brapi."
    assert payload["counters"] == {"brapi.timeout": 1}
    assert payload["total"] == 1


def test_integration_metrics_snapshot_can_reset_counters(app) -> None:
    reset_metrics_for_tests()
    increment_metric("brapi.http_error", amount=2)

    runner = app.test_cli_runner()
    reset_result = runner.invoke(
        args=["integration-metrics", "snapshot", "--prefix", "brapi.", "--reset"]
    )
    assert reset_result.exit_code == 0
    reset_payload = json.loads(reset_result.output.strip())
    assert reset_payload["counters"] == {"brapi.http_error": 2}
    assert reset_payload["total"] == 2

    after_reset_result = runner.invoke(
        args=["integration-metrics", "snapshot", "--prefix", "brapi."]
    )
    assert after_reset_result.exit_code == 0
    after_reset_payload = json.loads(after_reset_result.output.strip())
    assert after_reset_payload["counters"] == {}
    assert after_reset_payload["total"] == 0
