"""Per-user daily rate limit for AI insights endpoints (#1214).

Enforces a maximum of AI_DAILY_LIMIT calls per user per calendar day (BRT timezone).
The counter is backed by Redis when available; falls back to an in-process
dictionary for test environments where Redis is not configured.

Usage (in MethodResource views):
    @jwt_required()
    @ai_daily_limit()
    def get(self) -> Response:
        ...
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, TypeVar, cast
from uuid import UUID

from flask import Response

from app.controllers.response_contract import compat_error_response

_F = TypeVar("_F", bound=Callable[..., Any])

AI_DAILY_LIMIT = 2
AI_DAILY_LIMIT_ERROR_CODE = "AI_DAILY_LIMIT_EXCEEDED"
AI_DAILY_LIMIT_MESSAGE = (
    "Limite diário de insights atingido. "
    "Você pode gerar até 2 insights por dia. "
    "Tente novamente amanhã."
)

_BRT = timezone(timedelta(hours=-3))

# Module-level Redis client — initialised lazily, shared across requests.
_redis_lock = threading.Lock()
_redis_client: Any = None  # None = not yet initialised; False = unavailable
_REDIS_NOT_AVAILABLE = object()  # sentinel distinct from None


def _seconds_until_midnight_brt() -> int:
    """Seconds from now until 00:00 BRT of the next calendar day."""
    now = datetime.now(_BRT)
    midnight = datetime(now.year, now.month, now.day, tzinfo=_BRT) + timedelta(days=1)
    return max(1, int((midnight - now).total_seconds()))


def _brt_date_str() -> str:
    return datetime.now(_BRT).strftime("%Y-%m-%d")


def _get_redis() -> Any | None:
    """Return a connected Redis client or None if unavailable."""
    global _redis_client

    if _redis_client is _REDIS_NOT_AVAILABLE:
        return None

    with _redis_lock:
        if _redis_client is _REDIS_NOT_AVAILABLE:
            return None
        if _redis_client is not None:
            return _redis_client

        redis_url = (
            os.getenv("RATE_LIMIT_REDIS_URL") or os.getenv("REDIS_URL") or ""
        ).strip()
        if not redis_url:
            _redis_client = _REDIS_NOT_AVAILABLE
            return None

        try:
            import redis as _redis

            client = _redis.Redis.from_url(redis_url, socket_connect_timeout=1)
            client.ping()
            _redis_client = client
            return _redis_client
        except Exception:
            _redis_client = _REDIS_NOT_AVAILABLE
            return None


class _InMemoryAICounter:
    """Thread-safe in-memory counter — used when Redis is unavailable (tests)."""

    _counts: dict[str, int] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def incr(cls, key: str, ttl_seconds: int) -> int:  # noqa: ARG003
        with cls._lock:
            cls._counts[key] = cls._counts.get(key, 0) + 1
            return cls._counts[key]

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._counts.clear()


def check_ai_daily_limit(
    user_id: UUID,
    *,
    max_calls: int = AI_DAILY_LIMIT,
) -> tuple[int, int]:
    """Increment and return the daily AI call counter for *user_id*.

    Returns:
        (current_count, retry_after_seconds)

    A caller that receives current_count > max_calls MUST reject the request.
    """
    key = f"auraxis:ai-daily:{user_id}:{_brt_date_str()}"
    ttl = _seconds_until_midnight_brt()

    client = _get_redis()
    if client is not None:
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, ttl)
        return count, ttl

    return _InMemoryAICounter.incr(key, ttl), ttl


def ai_daily_limit(
    max_calls: int = AI_DAILY_LIMIT,
) -> Callable[[_F], _F]:
    """Decorator that enforces a per-user daily cap on AI insights endpoints.

    Must be applied AFTER @jwt_required() so that current_user_id() is available.

        @jwt_required()
        @ai_daily_limit()
        def get(self) -> Response: ...
    """

    def decorator(fn: _F) -> _F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Response:
            from app.auth import current_user_id
            from app.services.entitlement_service import has_entitlement

            user_id = current_user_id()

            # Only Premium users (advanced_simulations) can make manual AI insights
            # calls. Skip the rate-limit counter for Free users — the handler will
            # return 403 via its own entitlement gate.
            if not has_entitlement(user_id, "advanced_simulations"):
                return cast(Response, fn(*args, **kwargs))

            count, retry_after = check_ai_daily_limit(user_id, max_calls=max_calls)
            remaining = max(0, max_calls - count)

            if count > max_calls:
                resp = compat_error_response(
                    legacy_payload={"error": AI_DAILY_LIMIT_MESSAGE},
                    status_code=429,
                    message=AI_DAILY_LIMIT_MESSAGE,
                    error_code=AI_DAILY_LIMIT_ERROR_CODE,
                )
                resp.headers["Retry-After"] = str(retry_after)
                resp.headers["X-AI-Calls-Remaining"] = "0"
                return resp

            response = cast(Response, fn(*args, **kwargs))
            response.headers["X-AI-Calls-Remaining"] = str(remaining)
            return response

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "AI_DAILY_LIMIT",
    "AI_DAILY_LIMIT_ERROR_CODE",
    "AI_DAILY_LIMIT_MESSAGE",
    "ai_daily_limit",
    "check_ai_daily_limit",
    "_InMemoryAICounter",
    "_brt_date_str",
    "_seconds_until_midnight_brt",
]
