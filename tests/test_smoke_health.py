"""Smoke test for the health endpoint — DoD compliance for issue #617."""


def test_health_endpoint_returns_ok(client) -> None:
    """GET /healthz must return HTTP 200 with status=ok (public, no auth required)."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_health_endpoint_not_5xx(client) -> None:
    """GET /healthz must never return a 5xx response."""
    response = client.get("/healthz")
    assert response.status_code < 500
