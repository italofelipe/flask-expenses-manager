from __future__ import annotations

import importlib
import os
import threading
from collections import defaultdict, deque
from time import monotonic, time
from typing import Any, Deque, Protocol

__all__ = [
    "RateLimitStorage",
    "InMemoryRateLimitStorage",
    "RedisRateLimitStorage",
    "_build_storage_from_env",
]


class RateLimitStorage(Protocol):
    def consume(
        self,
        *,
        rule_name: str,
        key: str,
        window_seconds: int,
    ) -> tuple[int, int]:
        # Protocol contract only; concrete storage tracks per-window consumption.
        ...

    def reset(self) -> None:
        # Protocol contract only; tests may clear in-memory state.
        ...


class InMemoryRateLimitStorage:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(
        self,
        *,
        rule_name: str,
        key: str,
        window_seconds: int,
    ) -> tuple[int, int]:
        now = monotonic()
        bucket_key = (rule_name, key)
        with self._lock:
            events = self._events[bucket_key]
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            events.append(now)
            retry_after_seconds = max(1, int(window_seconds - (now - events[0])))
            return len(events), retry_after_seconds

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class RedisRateLimitStorage:
    def __init__(self, client: Any, *, key_prefix: str = "auraxis:rate-limit") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _window_slot(self, window_seconds: int) -> tuple[int, int]:
        now_seconds = int(time())
        slot = now_seconds // window_seconds
        retry_after_seconds = max(1, window_seconds - (now_seconds % window_seconds))
        return slot, retry_after_seconds

    def consume(
        self,
        *,
        rule_name: str,
        key: str,
        window_seconds: int,
    ) -> tuple[int, int]:
        slot, retry_after_seconds = self._window_slot(window_seconds)
        redis_key = f"{self._key_prefix}:{rule_name}:{key}:{slot}"
        consumed = int(self._client.incr(redis_key))
        if consumed == 1:
            self._client.expire(redis_key, window_seconds + 2)
        return consumed, retry_after_seconds

    def reset(self) -> None:
        # No-op for Redis backend in runtime paths.
        # Keys expire naturally by TTL.
        return None


def _build_storage_from_env() -> tuple[
    RateLimitStorage,
    str,
    bool,
    str,
    str | None,
]:
    backend = str(os.getenv("RATE_LIMIT_BACKEND", "memory")).strip().lower()
    if backend != "redis":
        return InMemoryRateLimitStorage(), "memory", True, "memory", None

    redis_url = str(
        os.getenv("RATE_LIMIT_REDIS_URL", os.getenv("REDIS_URL", ""))
    ).strip()
    if not redis_url:
        return (
            InMemoryRateLimitStorage(),
            "memory",
            False,
            "redis",
            "RATE_LIMIT_REDIS_URL not configured",
        )

    try:
        redis_client_cls = importlib.import_module("redis").Redis
    except Exception:
        return (
            InMemoryRateLimitStorage(),
            "memory",
            False,
            "redis",
            "redis package unavailable",
        )

    try:
        client = redis_client_cls.from_url(redis_url)
        client.ping()
    except Exception:
        return (
            InMemoryRateLimitStorage(),
            "memory",
            False,
            "redis",
            "redis backend unreachable",
        )
    return RedisRateLimitStorage(client), "redis", True, "redis", None
