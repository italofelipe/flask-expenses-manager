from __future__ import annotations

import importlib
import os
import threading
from dataclasses import dataclass
from typing import Any, Protocol

DEFAULT_LOGIN_GUARD_KEY_PREFIX = "auraxis:login-guard"


@dataclass
class LoginAttemptState:
    failures: int = 0
    blocked_until: float = 0.0
    updated_at: float = 0.0

    @classmethod
    def from_mapping(cls, mapping: dict[str, str]) -> "LoginAttemptState":
        return cls(
            failures=_safe_int(mapping.get("failures"), 0),
            blocked_until=_safe_float(mapping.get("blocked_until"), 0.0),
            updated_at=_safe_float(mapping.get("updated_at"), 0.0),
        )

    def to_mapping(self) -> dict[str, str]:
        return {
            "failures": str(self.failures),
            "blocked_until": f"{self.blocked_until:.6f}",
            "updated_at": f"{self.updated_at:.6f}",
        }


class LoginAttemptStorage(Protocol):
    def get(self, key: str) -> LoginAttemptState | None:
        # Protocol contract only; concrete backends provide state retrieval.
        ...

    def set(self, key: str, state: LoginAttemptState, *, ttl_seconds: int) -> None:
        # Protocol contract only; concrete backends persist state with TTL.
        ...

    def delete(self, key: str) -> None:
        # Protocol contract only; concrete backends remove persisted state.
        ...

    def prune(self, *, now: float, retention_seconds: int, max_keys: int) -> None:
        # Protocol contract only; backend chooses pruning implementation strategy.
        ...

    def reset_for_tests(self) -> None:
        # Protocol contract only; used by tests to clear backend state.
        ...


class InMemoryLoginAttemptStorage:
    def __init__(self) -> None:
        self._state: dict[str, LoginAttemptState] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> LoginAttemptState | None:
        with self._lock:
            state = self._state.get(key)
            if state is None:
                return None
            return LoginAttemptState(
                failures=state.failures,
                blocked_until=state.blocked_until,
                updated_at=state.updated_at,
            )

    def set(self, key: str, state: LoginAttemptState, *, ttl_seconds: int) -> None:
        del ttl_seconds
        with self._lock:
            self._state[key] = LoginAttemptState(
                failures=state.failures,
                blocked_until=state.blocked_until,
                updated_at=state.updated_at,
            )

    def delete(self, key: str) -> None:
        with self._lock:
            self._state.pop(key, None)

    def prune(self, *, now: float, retention_seconds: int, max_keys: int) -> None:
        with self._lock:
            if len(self._state) <= max_keys:
                return
            stale_keys = [
                key
                for key, value in self._state.items()
                if value.blocked_until <= now
                and (now - value.updated_at) >= retention_seconds
            ]
            for key in stale_keys:
                self._state.pop(key, None)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._state.clear()


class RedisLoginAttemptStorage:
    def __init__(
        self,
        client: Any,
        *,
        key_prefix: str = DEFAULT_LOGIN_GUARD_KEY_PREFIX,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _redis_key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    @staticmethod
    def _decode_mapping(raw_mapping: dict[Any, Any]) -> dict[str, str]:
        decoded: dict[str, str] = {}
        for raw_key, raw_value in raw_mapping.items():
            key = (
                raw_key.decode("utf-8")
                if isinstance(raw_key, (bytes, bytearray))
                else str(raw_key)
            )
            value = (
                raw_value.decode("utf-8")
                if isinstance(raw_value, (bytes, bytearray))
                else str(raw_value)
            )
            decoded[key] = value
        return decoded

    def get(self, key: str) -> LoginAttemptState | None:
        raw_mapping = self._client.hgetall(self._redis_key(key))
        if not raw_mapping:
            return None
        return LoginAttemptState.from_mapping(self._decode_mapping(raw_mapping))

    def set(self, key: str, state: LoginAttemptState, *, ttl_seconds: int) -> None:
        redis_key = self._redis_key(key)
        self._client.hset(redis_key, mapping=state.to_mapping())
        if ttl_seconds > 0:
            self._client.expire(redis_key, ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(self._redis_key(key))

    def prune(self, *, now: float, retention_seconds: int, max_keys: int) -> None:
        del now, retention_seconds, max_keys
        # Redis entries are pruned naturally by TTL.
        return None

    def reset_for_tests(self) -> None:
        scan_iter = getattr(self._client, "scan_iter", None)
        if scan_iter is None:
            return
        pattern = f"{self._key_prefix}:*"
        keys = list(scan_iter(match=pattern))
        if not keys:
            return
        self._client.delete(*keys)


def _safe_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _safe_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def build_login_attempt_storage_from_env() -> tuple[
    LoginAttemptStorage,
    str,
    bool,
    str,
    str | None,
]:
    backend = str(os.getenv("LOGIN_GUARD_BACKEND", "memory")).strip().lower()
    if backend != "redis":
        return InMemoryLoginAttemptStorage(), "memory", True, "memory", None

    redis_url = str(
        os.getenv("LOGIN_GUARD_REDIS_URL", os.getenv("REDIS_URL", ""))
    ).strip()
    if not redis_url:
        return (
            InMemoryLoginAttemptStorage(),
            "memory",
            False,
            "redis",
            "LOGIN_GUARD_REDIS_URL not configured",
        )

    try:
        redis_client_cls = getattr(importlib.import_module("redis"), "Redis")
    except Exception:
        return (
            InMemoryLoginAttemptStorage(),
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
            InMemoryLoginAttemptStorage(),
            "memory",
            False,
            "redis",
            "redis backend unreachable",
        )

    key_prefix = str(
        os.getenv("LOGIN_GUARD_REDIS_KEY_PREFIX", DEFAULT_LOGIN_GUARD_KEY_PREFIX)
    ).strip()
    return (
        RedisLoginAttemptStorage(
            client, key_prefix=key_prefix or DEFAULT_LOGIN_GUARD_KEY_PREFIX
        ),
        "redis",
        True,
        "redis",
        None,
    )
