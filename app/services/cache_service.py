"""
cache_service.py — Redis-backed cache for business queries.

Provides a thin, consistent interface (get / set / invalidate / invalidate_pattern)
with graceful degradation to a no-op when Redis is unavailable.  This ensures
a Redis outage never breaks business functionality.

TTLs
----
* Dashboard overview  : 300 s  (5 min) — invalidated on any transaction write
* BRAPI quotes        : 900 s  (15 min) — invalidated by TTL only
* Portfolio valuation : 600 s  (10 min) — invalidated on investment operation
* Entitlements        : 300 s  (5 min) — invalidated on grant/revoke/sync

Key patterns
------------
* ``dashboard:overview:{user_id}:{month}``
* ``brapi:quote:{ticker}``
* ``portfolio:valuation:{user_id}``
* ``entitlement:{user_id}:{feature_key}``

Usage
-----
    from app.services.cache_service import get_cache_service

    cache = get_cache_service()
    value = cache.get("dashboard:overview:uuid:2026-04")
    if value is None:
        value = _expensive_query()
        cache.set("dashboard:overview:uuid:2026-04", value, ttl=300)

    # Invalidate all dashboard keys for a user after a transaction write:
    cache.invalidate_pattern("dashboard:overview:{user_id}:*")
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── TTL constants ─────────────────────────────────────────────────────────────

DASHBOARD_CACHE_TTL = 300  # 5 minutes
BRAPI_CACHE_TTL = 900  # 15 minutes
PORTFOLIO_CACHE_TTL = 600  # 10 minutes
ENTITLEMENT_CACHE_TTL = 300  # 5 minutes — invalidated on grant/revoke/sync


# ── No-op fallback ────────────────────────────────────────────────────────────


class _NoOpCacheService:
    """Always returns cache-miss; used when Redis is unavailable."""

    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any, *, ttl: int) -> None:
        return None

    def invalidate(self, key: str) -> None:
        return None

    def invalidate_pattern(self, pattern: str) -> None:
        return None

    @property
    def available(self) -> bool:
        return False


# ── Redis-backed implementation ───────────────────────────────────────────────


class RedisCacheService:
    """Redis-backed cache service with JSON serialization."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, key: str) -> Any | None:
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            decoded = (
                raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
            )
            return json.loads(decoded)
        except Exception:
            logger.warning(
                "cache_service: GET failed key=%s — cache miss", key, exc_info=True
            )
            return None

    def set(self, key: str, value: Any, *, ttl: int) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception:
            logger.warning("cache_service: SET failed key=%s", key, exc_info=True)

    def invalidate(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception:
            logger.warning("cache_service: DELETE failed key=%s", key, exc_info=True)

    def invalidate_pattern(self, pattern: str) -> None:
        """Delete all keys matching a glob pattern (uses SCAN to avoid blocking)."""
        try:
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            logger.warning(
                "cache_service: invalidate_pattern failed pattern=%s",
                pattern,
                exc_info=True,
            )

    @property
    def available(self) -> bool:
        return True


# ── Singleton factory ─────────────────────────────────────────────────────────

_cache_instance: RedisCacheService | _NoOpCacheService | None = None


def _build_cache() -> RedisCacheService | _NoOpCacheService:
    redis_url = str(os.getenv("REDIS_URL", "")).strip()
    if not redis_url:
        logger.info("cache_service: REDIS_URL not set — using no-op cache")
        return _NoOpCacheService()

    try:
        redis_cls = importlib.import_module("redis").Redis
    except Exception:
        logger.warning("cache_service: redis package not available — using no-op cache")
        return _NoOpCacheService()

    try:
        client = redis_cls.from_url(redis_url, decode_responses=False)
        client.ping()
        logger.info("cache_service: Redis connected (%s)", redis_url.split("@")[-1])
        return RedisCacheService(client)
    except Exception:
        logger.warning(
            "cache_service: Redis connection failed — using no-op cache", exc_info=True
        )
        return _NoOpCacheService()


def get_cache_service() -> RedisCacheService | _NoOpCacheService:
    """Return the module-level cache singleton (built lazily on first call)."""
    global _cache_instance  # noqa: PLW0603
    if _cache_instance is None:
        _cache_instance = _build_cache()
    return _cache_instance


def reset_cache_service_for_tests() -> None:
    """Reset the singleton so tests can inject a fresh instance."""
    global _cache_instance  # noqa: PLW0603
    _cache_instance = None
