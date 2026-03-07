from __future__ import annotations

from flask import Flask

from app.http.request_context import (
    RequestContext,
    current_request_id,
    get_request_context,
    register_request_context_adapter,
)


def test_request_context_adapter_binds_request_metadata() -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.get("/ping")
    def _ping() -> tuple[str, int]:
        context = get_request_context()
        assert isinstance(context, RequestContext)
        assert context.method == "GET"
        assert context.path == "/ping"
        assert context.endpoint == "_ping"
        assert context.source_framework == "flask"
        assert context.user_agent == "pytest-agent"
        assert context.client_ip == "203.0.113.10"
        assert context.headers["x-real-ip"] == "203.0.113.10"
        assert context.trace_id == "trace-123"
        return "ok", 200

    register_request_context_adapter(app)

    client = app.test_client()
    response = client.get(
        "/ping",
        headers={
            "User-Agent": "pytest-agent",
            "X-Real-IP": "203.0.113.10",
            "X-Trace-Id": "trace-123",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]


def test_current_request_id_returns_default_outside_request() -> None:
    assert current_request_id() == "n/a"
