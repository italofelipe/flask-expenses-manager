from flask import Flask

from app.middleware.rate_limit import RateLimiterService, register_rate_limit_guard


def test_rate_limit_uses_memory_backend_by_default(monkeypatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)

    limiter = RateLimiterService.from_env()

    assert limiter.backend_name == "memory"


def test_rate_limit_falls_back_to_memory_when_redis_url_missing(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    limiter = RateLimiterService.from_env()

    assert limiter.backend_name == "memory"


def test_rate_limit_falls_back_to_memory_on_unreachable_redis(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "redis://127.0.0.1:6399/0")
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED", "false")

    limiter = RateLimiterService.from_env()

    assert limiter.backend_name == "memory"


def test_rate_limit_fail_closed_on_unavailable_redis(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED", "true")

    limiter = RateLimiterService.from_env()

    assert limiter.configured_backend == "redis"
    assert limiter.backend_ready is False
    assert limiter.fail_closed is True


def test_rate_limit_guard_returns_503_when_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED", "true")

    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.get("/probe")
    def _probe() -> tuple[str, int]:
        return "ok", 200

    register_rate_limit_guard(app)

    client = app.test_client()
    response = client.get("/probe")

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"] == "RATE_LIMIT_BACKEND_UNAVAILABLE"
