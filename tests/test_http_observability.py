from __future__ import annotations

import logging

import pytest
from flask import g

from app.extensions.integration_metrics import (
    build_http_latency_budget_payload,
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
    assert envelope.status_class == "2xx"
    assert envelope.is_error is False
    assert envelope.source_framework == "flask"
    assert envelope.trace_id == "trace-123"
    assert envelope.auth_subject is None
    assert envelope.duration_ms >= 0


def test_build_observability_envelope_includes_graphql_correlation(app) -> None:
    with app.test_request_context(
        "/graphql",
        method="POST",
        headers={"X-Trace-Id": "trace-graphql-123"},
    ):
        bind_request_context()
        mark_request_start()
        g.graphql_operation_name = "Me"
        g.graphql_root_fields = ("me",)

        response = app.response_class(status=401)
        envelope = build_observability_envelope(response)

    assert envelope is not None
    assert envelope.status_class == "4xx"
    assert envelope.is_error is True
    assert envelope.trace_id == "trace-graphql-123"
    assert envelope.graphql_operation_name == "Me"
    assert envelope.graphql_root_fields == ("me",)


def test_http_observability_logs_and_tracks_metrics(
    client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    reset_metrics_for_tests()

    with caplog.at_level(logging.INFO):
        response = client.get("/healthz", headers={"X-Trace-Id": "trace-health-123"})

    assert response.status_code == 200

    logs = [
        record.message
        for record in caplog.records
        if "http_observability " in record.message
    ]
    assert len(logs) == 1
    assert "trace_id=trace-health-123" in logs[0]
    assert "source_framework=flask" in logs[0]
    assert "route=health.healthz" in logs[0]
    assert "status=200" in logs[0]
    assert "status_class=2xx" in logs[0]
    assert "is_error=false" in logs[0]

    payload = build_http_observability_metrics_payload()
    assert payload["summary"]["requests_total"] >= 1
    assert payload["summary"]["flask_requests"] >= 1
    assert payload["summary"]["anonymous"] >= 1
    assert payload["summary"]["trace_present"] >= 1
    assert payload["summary"]["status_2xx"] >= 1
    assert payload["summary"]["duration_ms_total"] >= 0

    latency_payload = build_http_latency_budget_payload()
    health_route = latency_payload["routes"]["health.healthz"]
    assert health_route["samples"] >= 1
    assert health_route["budget_ms"] == 100
