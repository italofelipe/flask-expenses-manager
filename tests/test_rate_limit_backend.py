from app.middleware.rate_limit import RateLimiterService


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

    limiter = RateLimiterService.from_env()

    assert limiter.backend_name == "memory"
