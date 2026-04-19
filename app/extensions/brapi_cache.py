"""Redis cache for BRAPI market data (investment price lookups).

Mirrors the pattern of jwt_revocation_cache — Redis when available,
no-op fallback otherwise so that a Redis outage never breaks pricing.

Cache key: ``brapi:cache:{key}``
TTL:       controlled by ``BRAPI_CACHE_TTL_SECONDS`` (default 60 s).
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_KEY_PREFIX = "brapi:cache"


class _NoOpBrapiCache:
    """Always reports a cache-miss; used when Redis is unavailable or TTL=0."""

    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        pass

    def reset(self) -> None:
        pass


class RedisBrapiCache:
    """Redis-backed BRAPI market data cache."""

    def __init__(self, client: Any, *, key_prefix: str = _KEY_PREFIX) -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    def get(self, key: str) -> Any | None:
        try:
            raw = self._client.get(self._key(key))
            if raw is None:
                return None
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except Exception:
            logger.warning(
                "brapi_cache: Redis GET failed key=%s — cache miss", key, exc_info=True
            )
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        try:
            self._client.setex(self._key(key), ttl_seconds, json.dumps(value))
        except Exception:
            logger.warning("brapi_cache: Redis SETEX failed key=%s", key, exc_info=True)

    def reset(self) -> None:
        try:
            keys = self._client.keys(f"{self._key_prefix}:*")
            if keys:
                self._client.delete(*keys)
        except Exception:
            logger.warning("brapi_cache: Redis reset failed", exc_info=True)


_cache_instance: RedisBrapiCache | _NoOpBrapiCache | _MemoryBrapiCache | None = None


def _build_cache() -> RedisBrapiCache | _NoOpBrapiCache:
    redis_url = str(os.getenv("REDIS_URL", "")).strip()
    if not redis_url:
        logger.info("brapi_cache: REDIS_URL not set — using no-op")
        return _NoOpBrapiCache()

    try:
        redis_cls = importlib.import_module("redis").Redis
    except Exception:
        logger.warning("brapi_cache: redis package unavailable — using no-op")
        return _NoOpBrapiCache()

    try:
        client = redis_cls.from_url(redis_url)
        client.ping()
    except Exception:
        logger.warning("brapi_cache: Redis unreachable — using no-op")
        return _NoOpBrapiCache()

    logger.info(
        "brapi_cache: Redis backend active url=%s prefix=%s", redis_url, _KEY_PREFIX
    )
    return RedisBrapiCache(client)


def get_brapi_cache() -> RedisBrapiCache | _NoOpBrapiCache | _MemoryBrapiCache:
    """Return the module-level cache singleton (built lazily on first call)."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = _build_cache()
    return _cache_instance


class _MemoryBrapiCache:
    """Simple dict-backed cache for unit tests — not for production use."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds > 0:
            self._store[key] = value

    def reset(self) -> None:
        self._store.clear()


def reset_brapi_cache_for_tests() -> None:
    """Reset the singleton so tests can inject a fresh instance."""
    global _cache_instance
    _cache_instance = None


def inject_memory_cache_for_tests() -> _MemoryBrapiCache:
    """Replace the singleton with an in-memory cache and return it.

    Allows test assertions about what was stored without requiring Redis.
    """
    global _cache_instance
    mem = _MemoryBrapiCache()
    _cache_instance = mem
    return mem
