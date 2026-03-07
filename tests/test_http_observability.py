from __future__ import annotations

import logging

import pytest

from app.extensions.integration_metrics import (
    build_http_observability_metrics_payload,
    reset_metrics_for_tests,
)
from app.http import build_observability_envelope
from app.http.observability import mark_request_start
from app.http.request_context import bind_request_context


def test_build_observability_envelope_uses_request_context(app) -> None:
    with app.test_request_context(
        "/healthz",
        method="GET",
        headers={"User-Agent": "pytest-agent", "X-Trace-Id": "trace-123"},
    ):
        bind_request_context()
        mark_request_start()

        response = app.response_class(status=204)
        envelope = build_observability_envelope(response)

    assert envelope is not None
    assert envelope.route == "health.healthz"
    assert envelope.method == "GET"
    assert envelope.status_code == 204
    assert envelope.source_framework == "flask"
    assert envelope.auth_subject is None
    assert envelope.duration_ms >= 0


def test_http_observability_logs_and_tracks_metrics(
    client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    reset_metrics_for_tests()

    with caplog.at_level(logging.INFO):
        response = client.get("/healthz")

    assert response.status_code == 200

    logs = [
        record.message
        for record in caplog.records
        if "http_observability " in record.message
    ]
    assert len(logs) == 1
    assert "source_framework=flask" in logs[0]
    assert "route=health.healthz" in logs[0]
    assert "status=200" in logs[0]

    payload = build_http_observability_metrics_payload()
    assert payload["summary"]["requests_total"] >= 1
    assert payload["summary"]["flask_requests"] >= 1
    assert payload["summary"]["anonymous"] >= 1
    assert payload["summary"]["duration_ms_total"] >= 0
