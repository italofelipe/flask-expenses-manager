from __future__ import annotations

from app.extensions.integration_metrics import (
    increment_metric,
    record_metric_sample,
    reset_metrics_for_tests,
)


def test_observability_snapshot_returns_404_when_disabled(client) -> None:
    reset_metrics_for_tests()

    response = client.get("/ops/observability")

    assert response.status_code == 404


def test_observability_snapshot_requires_token(client, monkeypatch) -> None:
    reset_metrics_for_tests()
    monkeypatch.setenv("OBSERVABILITY_EXPORT_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_EXPORT_TOKEN", "secret-token")

    response = client.get("/ops/observability")

    assert response.status_code == 401


def test_observability_snapshot_returns_export_payload(client, monkeypatch) -> None:
    reset_metrics_for_tests()
    monkeypatch.setenv("OBSERVABILITY_EXPORT_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_EXPORT_TOKEN", "secret-token")
    increment_metric("graphql.request.total")
    increment_metric("http.request.total", amount=2)
    record_metric_sample("http.route.duration_ms.transaction_list", 120)
    record_metric_sample("http.route.duration_ms.transaction_list", 180)

    response = client.get(
        "/ops/observability",
        headers={"X-Observability-Key": "secret-token"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["component"] == "observability_export"
    assert body["components"]["graphql"]["summary"]["requests_total"] == 1
    assert body["components"]["http"]["summary"]["requests_total"] == 2


def test_observability_metrics_returns_prometheus_payload(client, monkeypatch) -> None:
    reset_metrics_for_tests()
    monkeypatch.setenv("OBSERVABILITY_EXPORT_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_EXPORT_TOKEN", "secret-token")
    increment_metric("graphql.request.total")
    record_metric_sample("http.route.duration_ms.transaction_list", 90)
    record_metric_sample("http.route.duration_ms.transaction_list", 150)

    response = client.get(
        "/ops/metrics",
        headers={"X-Observability-Key": "secret-token"},
    )

    assert response.status_code == 200
    payload = response.get_data(as_text=True)
    assert "auraxis_graphql_request_total 1" in payload
    assert "auraxis_http_route_duration_ms_transaction_list_count 2" in payload
    assert "auraxis_http_route_duration_ms_transaction_list_p95" in payload
