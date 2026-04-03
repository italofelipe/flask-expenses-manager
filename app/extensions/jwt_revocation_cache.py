"""Redis cache for JWT revocation checks.

Caches the current_jti value per user to avoid a DB hit on every authenticated
request.  Falls back to a no-op (always cache-miss) when Redis is unavailable,
so that a Redis outage never locks out legitimate users.

Cache key: ``jwt:revoked:{user_id}``
TTL:       300 seconds (configurable via ``JWT_REVOCATION_CACHE_TTL``).

Usage::

    from app.extensions.jwt_revocation_cache import get_jwt_revocation_cache

    cache = get_jwt_revocation_cache()
    jti = cache.get_current_jti(user_id)   # None on cache-miss or Redis down
    cache.set_current_jti(user_id, jti)
    cache.invalidate(user_id)
"""

from __future__ import annotations

import importlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_KEY_PREFIX = "jwt:revoked"
DEFAULT_TTL_SECONDS = 300


class _NoOpJwtRevocationCache:
    """Always reports a cache-miss; used when Redis is unavailable."""

    def get_current_jti(self, user_id: str) -> str | None:
        return None

    def set_current_jti(self, user_id: str, jti: str | None) -> None:
        return None

    def invalidate(self, user_id: str) -> None:
        return None


class RedisJwtRevocationCache:
    """Redis-backed JWT revocation cache."""

    def __init__(
        self,
        client: Any,
        *,
        key_prefix: str = DEFAULT_KEY_PREFIX,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    def _key(self, user_id: str) -> str:
        return f"{self._key_prefix}:{user_id}"

    def get_current_jti(self, user_id: str) -> str | None:
        try:
            raw = self._client.get(self._key(user_id))
            if raw is None:
                return None
            if isinstance(raw, (bytes, bytearray)):
                return raw.decode("utf-8")
            return str(raw)
        except Exception:
            logger.warning(
                "jwt_revocation_cache: Redis GET failed for user_id=%s — cache miss",
                user_id,
                exc_info=True,
            )
            return None

    def set_current_jti(self, user_id: str, jti: str | None) -> None:
        if jti is None:
            self.invalidate(user_id)
            return
        try:
            self._client.setex(self._key(user_id), self._ttl_seconds, jti)
        except Exception:
            logger.warning(
                "jwt_revocation_cache: Redis SETEX failed for user_id=%s",
                user_id,
                exc_info=True,
            )

    def invalidate(self, user_id: str) -> None:
        try:
            self._client.delete(self._key(user_id))
        except Exception:
            logger.warning(
                "jwt_revocation_cache: Redis DELETE failed for user_id=%s",
                user_id,
                exc_info=True,
            )


# Module-level singleton — built once at first use.
_cache_instance: RedisJwtRevocationCache | _NoOpJwtRevocationCache | None = None


def _build_cache() -> RedisJwtRevocationCache | _NoOpJwtRevocationCache:
    redis_url = str(
        os.getenv("JWT_REVOCATION_REDIS_URL", os.getenv("REDIS_URL", ""))
    ).strip()
    if not redis_url:
        logger.info(
            "jwt_revocation_cache: REDIS_URL not set — using no-op (DB fallback active)"
        )
        return _NoOpJwtRevocationCache()

    try:
        redis_cls = importlib.import_module("redis").Redis
    except Exception:
        logger.warning("jwt_revocation_cache: redis package unavailable — using no-op")
        return _NoOpJwtRevocationCache()

    try:
        client = redis_cls.from_url(redis_url)
        client.ping()
    except Exception:
        logger.warning(
            "jwt_revocation_cache: Redis unreachable — using no-op (DB fallback active)"
        )
        return _NoOpJwtRevocationCache()

    ttl = int(os.getenv("JWT_REVOCATION_CACHE_TTL", str(DEFAULT_TTL_SECONDS)))
    key_prefix = str(
        os.getenv("JWT_REVOCATION_CACHE_KEY_PREFIX", DEFAULT_KEY_PREFIX)
    ).strip()
    logger.info(
        "jwt_revocation_cache: Redis backend active (url=%s ttl=%ds prefix=%s)",
        redis_url,
        ttl,
        key_prefix,
    )
    return RedisJwtRevocationCache(
        client,
        key_prefix=key_prefix or DEFAULT_KEY_PREFIX,
        ttl_seconds=ttl,
    )


def get_jwt_revocation_cache() -> RedisJwtRevocationCache | _NoOpJwtRevocationCache:
    """Return the module-level cache singleton (built lazily on first call)."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = _build_cache()
    return _cache_instance


def reset_jwt_revocation_cache_for_tests() -> None:
    """Reset the singleton so tests can inject a fresh instance."""
    global _cache_instance
    _cache_instance = None
