"""Unit tests for brapi_cache.py — covers Redis, no-op, and memory paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.extensions.brapi_cache import (
    RedisBrapiCache,
    _MemoryBrapiCache,
    _NoOpBrapiCache,
    get_brapi_cache,
    inject_memory_cache_for_tests,
    reset_brapi_cache_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_brapi_cache_for_tests()
    yield
    reset_brapi_cache_for_tests()


class TestNoOpBrapiCache:
    def test_get_always_returns_none(self):
        cache = _NoOpBrapiCache()
        assert cache.get("any-key") is None

    def test_set_is_silent(self):
        cache = _NoOpBrapiCache()
        cache.set("key", {"value": 1}, ttl_seconds=60)

    def test_reset_is_silent(self):
        cache = _NoOpBrapiCache()
        cache.reset()


class TestMemoryBrapiCache:
    def test_set_and_get_roundtrip(self):
        cache = _MemoryBrapiCache()
        cache.set("k", 42.0, ttl_seconds=60)
        assert cache.get("k") == 42.0

    def test_set_with_ttl_zero_does_not_store(self):
        cache = _MemoryBrapiCache()
        cache.set("k", 99, ttl_seconds=0)
        assert cache.get("k") is None

    def test_get_missing_key_returns_none(self):
        cache = _MemoryBrapiCache()
        assert cache.get("missing") is None

    def test_reset_clears_all(self):
        cache = _MemoryBrapiCache()
        cache.set("a", 1, ttl_seconds=60)
        cache.set("b", 2, ttl_seconds=60)
        cache.reset()
        assert cache.get("a") is None
        assert cache.get("b") is None


class TestRedisBrapiCache:
    def _make_client(self) -> MagicMock:
        return MagicMock()

    def test_set_calls_setex_with_correct_args(self):
        client = self._make_client()
        cache = RedisBrapiCache(client)
        cache.set("PETR4", 32.5, ttl_seconds=60)
        client.setex.assert_called_once()
        args = client.setex.call_args[0]
        assert args[0] == "brapi:cache:PETR4"
        assert args[1] == 60

    def test_set_skips_when_ttl_zero(self):
        client = self._make_client()
        cache = RedisBrapiCache(client)
        cache.set("VALE3", 10.0, ttl_seconds=0)
        client.setex.assert_not_called()

    def test_set_skips_when_ttl_negative(self):
        client = self._make_client()
        cache = RedisBrapiCache(client)
        cache.set("VALE3", 10.0, ttl_seconds=-1)
        client.setex.assert_not_called()

    def test_get_returns_parsed_json(self):
        import json

        client = self._make_client()
        client.get.return_value = json.dumps({"price": 15.0}).encode("utf-8")
        cache = RedisBrapiCache(client)
        result = cache.get("ITUB4")
        assert result == {"price": 15.0}

    def test_get_decodes_bytes(self):
        import json

        client = self._make_client()
        client.get.return_value = json.dumps(42.5).encode("utf-8")
        cache = RedisBrapiCache(client)
        assert cache.get("BBAS3") == 42.5

    def test_get_returns_none_on_cache_miss(self):
        client = self._make_client()
        client.get.return_value = None
        cache = RedisBrapiCache(client)
        assert cache.get("NONEXISTENT") is None

    def test_get_returns_none_on_redis_error(self):
        client = self._make_client()
        client.get.side_effect = Exception("Redis unavailable")
        cache = RedisBrapiCache(client)
        assert cache.get("ERRKEY") is None

    def test_set_swallows_redis_exception(self):
        client = self._make_client()
        client.setex.side_effect = Exception("Redis write error")
        cache = RedisBrapiCache(client)
        cache.set("KEY", 1.0, ttl_seconds=60)

    def test_reset_deletes_all_prefixed_keys(self):
        client = self._make_client()
        client.keys.return_value = [b"brapi:cache:A", b"brapi:cache:B"]
        cache = RedisBrapiCache(client)
        cache.reset()
        client.delete.assert_called_once_with(b"brapi:cache:A", b"brapi:cache:B")

    def test_reset_skips_delete_when_no_keys(self):
        client = self._make_client()
        client.keys.return_value = []
        cache = RedisBrapiCache(client)
        cache.reset()
        client.delete.assert_not_called()

    def test_reset_swallows_exception(self):
        client = self._make_client()
        client.keys.side_effect = Exception("Redis unavailable")
        cache = RedisBrapiCache(client)
        cache.reset()


class TestBuildCache:
    def test_returns_noop_when_redis_url_not_set(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        reset_brapi_cache_for_tests()
        result = get_brapi_cache()
        assert isinstance(result, _NoOpBrapiCache)

    def test_returns_noop_when_redis_package_unavailable(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        reset_brapi_cache_for_tests()
        with patch("importlib.import_module", side_effect=ImportError("no redis")):
            result = get_brapi_cache()
        assert isinstance(result, _NoOpBrapiCache)

    def test_returns_noop_when_redis_unreachable(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:19999")
        reset_brapi_cache_for_tests()
        mock_redis_cls = MagicMock()
        mock_client = MagicMock()
        mock_client.ping.side_effect = Exception("connection refused")
        mock_redis_cls.from_url.return_value = mock_client
        mock_module = MagicMock()
        mock_module.Redis = mock_redis_cls
        with patch("importlib.import_module", return_value=mock_module):
            result = get_brapi_cache()
        assert isinstance(result, _NoOpBrapiCache)

    def test_returns_redis_cache_when_reachable(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        reset_brapi_cache_for_tests()
        mock_redis_cls = MagicMock()
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis_cls.from_url.return_value = mock_client
        mock_module = MagicMock()
        mock_module.Redis = mock_redis_cls
        with patch("importlib.import_module", return_value=mock_module):
            result = get_brapi_cache()
        assert isinstance(result, RedisBrapiCache)

    def test_singleton_returns_same_instance(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        reset_brapi_cache_for_tests()
        a = get_brapi_cache()
        b = get_brapi_cache()
        assert a is b

    def test_inject_memory_cache_replaces_singleton(self):
        mem = inject_memory_cache_for_tests()
        assert get_brapi_cache() is mem
        assert isinstance(mem, _MemoryBrapiCache)
