from flask import Flask

from app.extensions.integration_metrics import reset_metrics_for_tests, snapshot_metrics
from app.middleware.rate_limit import register_rate_limit_guard


def test_rate_limit_metrics_increment_for_allowed_and_blocked_requests(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_WINDOW_SECONDS", "60")

    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.get("/probe")
    def _probe() -> tuple[str, int]:
        return "ok", 200

    register_rate_limit_guard(app)
    reset_metrics_for_tests()

    client = app.test_client()
    first = client.get("/probe")
    second = client.get("/probe")

    assert first.status_code == 200
    assert second.status_code == 429
    metrics = snapshot_metrics(prefix="rate_limit.")
    assert metrics["rate_limit.allowed"] >= 1
    assert metrics["rate_limit.allowed.default"] >= 1
    assert metrics["rate_limit.blocked"] >= 1
    assert metrics["rate_limit.blocked.default"] >= 1


def test_rate_limit_metrics_increment_when_redis_backend_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED", "true")
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.get("/probe")
    def _probe() -> tuple[str, int]:
        return "ok", 200

    register_rate_limit_guard(app)
    reset_metrics_for_tests()

    response = app.test_client().get("/probe")

    assert response.status_code == 503
    metrics = snapshot_metrics(prefix="rate_limit.")
    assert metrics["rate_limit.backend_unavailable"] >= 1
