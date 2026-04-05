"""Tests for CacheService — covers hit, miss, invalidation, and fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.cache_service import (
    RedisCacheService,
    _NoOpCacheService,
    get_cache_service,
    reset_cache_service_for_tests,
)

# ── _NoOpCacheService ─────────────────────────────────────────────────────────


def test_noop_get_returns_none() -> None:
    cache = _NoOpCacheService()
    assert cache.get("any:key") is None


def test_noop_set_is_silent() -> None:
    cache = _NoOpCacheService()
    cache.set("any:key", {"foo": "bar"}, ttl=60)  # must not raise


def test_noop_invalidate_is_silent() -> None:
    cache = _NoOpCacheService()
    cache.invalidate("any:key")  # must not raise
    cache.invalidate_pattern("any:*")  # must not raise


def test_noop_not_available() -> None:
    assert _NoOpCacheService().available is False


# ── RedisCacheService — happy path ────────────────────────────────────────────


def _make_redis_cache() -> tuple[RedisCacheService, MagicMock]:
    client = MagicMock()
    return RedisCacheService(client), client


def test_cache_miss_returns_none() -> None:
    cache, client = _make_redis_cache()
    client.get.return_value = None
    assert cache.get("dashboard:overview:uid:2026-04") is None


def test_cache_hit_deserializes_json() -> None:
    cache, client = _make_redis_cache()
    client.get.return_value = b'{"balance": 1500.0}'
    result = cache.get("dashboard:overview:uid:2026-04")
    assert result == {"balance": 1500.0}


def test_cache_set_calls_setex() -> None:
    cache, client = _make_redis_cache()
    cache.set("dashboard:overview:uid:2026-04", {"balance": 1500.0}, ttl=300)
    client.setex.assert_called_once()
    call_args = client.setex.call_args
    assert call_args[0][0] == "dashboard:overview:uid:2026-04"
    assert call_args[0][1] == 300
    assert '"balance"' in call_args[0][2]


def test_cache_invalidate_calls_delete() -> None:
    cache, client = _make_redis_cache()
    cache.invalidate("dashboard:overview:uid:2026-04")
    client.delete.assert_called_once_with("dashboard:overview:uid:2026-04")


def test_cache_invalidate_pattern_uses_scan() -> None:
    cache, client = _make_redis_cache()
    client.scan.return_value = (0, [b"dashboard:overview:uid:2026-04"])
    cache.invalidate_pattern("dashboard:overview:uid:*")
    client.scan.assert_called_once()
    client.delete.assert_called_once_with(b"dashboard:overview:uid:2026-04")


def test_cache_available() -> None:
    cache, _ = _make_redis_cache()
    assert cache.available is True


# ── RedisCacheService — fallback on Redis errors ──────────────────────────────


def test_get_returns_none_on_redis_error() -> None:
    cache, client = _make_redis_cache()
    client.get.side_effect = ConnectionError("Redis down")
    assert cache.get("key") is None  # must not raise


def test_set_is_silent_on_redis_error() -> None:
    cache, client = _make_redis_cache()
    client.setex.side_effect = ConnectionError("Redis down")
    cache.set("key", {"x": 1}, ttl=60)  # must not raise


def test_invalidate_is_silent_on_redis_error() -> None:
    cache, client = _make_redis_cache()
    client.delete.side_effect = ConnectionError("Redis down")
    cache.invalidate("key")  # must not raise


def test_invalidate_pattern_is_silent_on_redis_error() -> None:
    cache, client = _make_redis_cache()
    client.scan.side_effect = ConnectionError("Redis down")
    cache.invalidate_pattern("dashboard:*")  # must not raise


# ── Singleton / factory ───────────────────────────────────────────────────────


def test_get_cache_service_returns_noop_without_redis_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    reset_cache_service_for_tests()
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache = get_cache_service()
    assert isinstance(cache, _NoOpCacheService)
    reset_cache_service_for_tests()


def test_get_cache_service_returns_noop_on_connection_failure(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    reset_cache_service_for_tests()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    with patch("importlib.import_module") as mock_import:
        mock_redis_cls = MagicMock()
        mock_redis_cls.from_url.return_value.ping.side_effect = ConnectionError(
            "refused"
        )
        mock_import.return_value.Redis = mock_redis_cls
        cache = get_cache_service()
    assert isinstance(cache, _NoOpCacheService)
    reset_cache_service_for_tests()
