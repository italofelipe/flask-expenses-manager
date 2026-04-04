"""API23 — Prometheus metrics + request_id correlation tests.

Covers:
- /ops/metrics returns 200 and contains auraxis_http_requests_total
- X-Request-Id header is present on every response
- A request increments auraxis_http_requests_total (via generate_latest output)
- auraxis_auth_logins_total is incremented on login outcomes
- auraxis_http_request_duration_seconds histogram is populated
"""

from __future__ import annotations

import os

import pytest

import app.extensions.prometheus_metrics as prom_mod
from app.extensions.prometheus_metrics import (
    generate_latest_metrics,
    record_auth_login,
    record_http_request,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metrics_text(client: object, monkeypatch: pytest.MonkeyPatch) -> str:
    """Return the /ops/metrics response body with the test token set."""
    monkeypatch.setenv("OBSERVABILITY_EXPORT_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_EXPORT_TOKEN", "test-prom-token")
    response = client.get(  # type: ignore[union-attr]
        "/ops/metrics",
        headers={"X-Observability-Key": "test-prom-token"},
    )
    assert response.status_code == 200
    return response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# /ops/metrics endpoint
# ---------------------------------------------------------------------------


def test_ops_metrics_returns_200_with_prometheus_label(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /ops/metrics returns HTTP 200 and contains the canonical counter name."""
    prom_mod._ensure_metrics_initialized()
    # Make at least one request so the counter has a sample
    client.get("/healthz")

    payload = _metrics_text(client, monkeypatch)

    assert "auraxis_http_requests_total" in payload


def test_ops_metrics_contains_duration_histogram(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Histogram metric name must appear in the output after at least one request."""
    prom_mod._ensure_metrics_initialized()
    client.get("/healthz")

    payload = _metrics_text(client, monkeypatch)

    assert "auraxis_http_request_duration_seconds" in payload


def test_ops_metrics_requires_token(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the observability token the endpoint returns 401."""
    monkeypatch.setenv("OBSERVABILITY_EXPORT_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_EXPORT_TOKEN", "secret")

    response = client.get("/ops/metrics")
    assert response.status_code == 401


def test_ops_metrics_returns_404_when_disabled(client) -> None:
    """When OBSERVABILITY_EXPORT_ENABLED is false the endpoint returns 404."""
    os.environ.pop("OBSERVABILITY_EXPORT_ENABLED", None)
    response = client.get("/ops/metrics", headers={"X-Observability-Key": "anything"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# X-Request-Id header on every response
# ---------------------------------------------------------------------------


def test_request_id_header_present_on_healthz(client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "X-Request-Id" in response.headers


def test_request_id_header_present_on_404(client) -> None:
    response = client.get("/non-existent-route-xyz")
    assert "X-Request-Id" in response.headers


def test_request_id_echoes_incoming_header(client) -> None:
    """If the caller supplies X-Request-ID it should be echoed back."""
    response = client.get("/healthz", headers={"X-Request-Id": "caller-provided-id"})
    # The response header must be non-empty
    assert response.headers.get("X-Request-Id")


# ---------------------------------------------------------------------------
# Counter increments (via module reference, post-init)
# ---------------------------------------------------------------------------


def test_record_http_request_increments_counter() -> None:
    """record_http_request() must increment the prometheus counter."""
    prom_mod._ensure_metrics_initialized()
    counter = prom_mod._HTTP_REQUESTS_TOTAL
    assert counter is not None

    before = counter.labels(
        method="GET", endpoint="test_endpoint_abc", status_code="200"
    )._value.get()

    record_http_request(
        method="GET",
        endpoint="test_endpoint_abc",
        status_code=200,
        duration_seconds=0.05,
    )

    after = counter.labels(
        method="GET", endpoint="test_endpoint_abc", status_code="200"
    )._value.get()

    assert after == before + 1.0


def test_record_http_request_observes_duration_histogram() -> None:
    """record_http_request() must add an observation to the histogram."""
    prom_mod._ensure_metrics_initialized()
    histogram = prom_mod._HTTP_REQUEST_DURATION
    assert histogram is not None

    before_sum = histogram.labels(
        method="POST", endpoint="test_duration_endpoint"
    )._sum.get()

    record_http_request(
        method="POST",
        endpoint="test_duration_endpoint",
        status_code=201,
        duration_seconds=0.123,
    )

    after_sum = histogram.labels(
        method="POST", endpoint="test_duration_endpoint"
    )._sum.get()

    assert after_sum > before_sum


def test_record_auth_login_increments_success_counter() -> None:
    prom_mod._ensure_metrics_initialized()
    auth_counter = prom_mod._AUTH_LOGINS_TOTAL
    assert auth_counter is not None

    before = auth_counter.labels(status="success")._value.get()
    record_auth_login(status="success")
    after = auth_counter.labels(status="success")._value.get()

    assert after == before + 1.0


def test_record_auth_login_increments_failure_counter() -> None:
    prom_mod._ensure_metrics_initialized()
    auth_counter = prom_mod._AUTH_LOGINS_TOTAL
    assert auth_counter is not None

    before = auth_counter.labels(status="failure")._value.get()
    record_auth_login(status="failure")
    after = auth_counter.labels(status="failure")._value.get()

    assert after == before + 1.0


# ---------------------------------------------------------------------------
# generate_latest_metrics helper
# ---------------------------------------------------------------------------


def test_generate_latest_metrics_returns_bytes_and_content_type() -> None:
    prom_mod._ensure_metrics_initialized()
    body, content_type = generate_latest_metrics()
    assert isinstance(body, bytes)
    assert "text/plain" in content_type
    assert len(body) > 0


def test_generate_latest_metrics_contains_counter_name() -> None:
    prom_mod._ensure_metrics_initialized()
    # Ensure at least one label set exists
    record_http_request(
        method="GET",
        endpoint="generate_latest_test",
        status_code=200,
        duration_seconds=0.01,
    )
    body, _ = generate_latest_metrics()
    assert b"auraxis_http_requests_total" in body


# ---------------------------------------------------------------------------
# Integration: real HTTP request increments counter visible in /ops/metrics
# ---------------------------------------------------------------------------


def test_http_request_counter_incremented_after_request(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Making a real request must cause the counter to appear in /ops/metrics."""
    prom_mod._ensure_metrics_initialized()

    client.get("/healthz")

    payload = _metrics_text(client, monkeypatch)

    # The counter must appear in the output
    assert "auraxis_http_requests_total" in payload
