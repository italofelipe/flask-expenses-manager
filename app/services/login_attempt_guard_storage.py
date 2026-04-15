from __future__ import annotations

import importlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

_logger = logging.getLogger("auraxis.login_guard")

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
        redis_client_cls = importlib.import_module("redis").Redis
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
    redis_storage = RedisLoginAttemptStorage(
        client, key_prefix=key_prefix or DEFAULT_LOGIN_GUARD_KEY_PREFIX
    )
    probe_interval = int(os.getenv("LOGIN_GUARD_PROBE_INTERVAL_SECONDS", "30"))
    failover_storage = FailoverLoginAttemptStorage(
        redis=redis_storage,
        probe_interval_seconds=max(10, probe_interval),
    )
    return (
        failover_storage,
        "redis",
        True,
        "redis",
        None,
    )


# ── FailoverLoginAttemptStorage ───────────────────────────────────────────────

_FAILOVER_PROBE_INTERVAL_DEFAULT = 30  # seconds between Redis health probes
_FAILOVER_MAX_MEMORY_KEYS = 10_000  # hard cap; LRU-style eviction via prune()


class FailoverLoginAttemptStorage:
    """Redis-backed storage with automatic in-memory fallback.

    Normal operation: all operations delegate to ``RedisLoginAttemptStorage``.

    On any Redis exception: switches to ``InMemoryLoginAttemptStorage`` and
    starts a background probe thread.  When Redis becomes reachable again the
    in-memory state is flushed to Redis and the primary backend is restored.

    The probe runs at most once every *probe_interval_seconds* to avoid
    hammering a recovering Redis.
    """

    def __init__(
        self,
        *,
        redis: RedisLoginAttemptStorage,
        probe_interval_seconds: int = _FAILOVER_PROBE_INTERVAL_DEFAULT,
    ) -> None:
        self._redis = redis
        self._memory = InMemoryLoginAttemptStorage()
        self._probe_interval = probe_interval_seconds
        self._using_fallback = False
        self._lock = threading.Lock()
        self._probe_thread: threading.Thread | None = None
        self._last_probe_at: float = 0.0

    # ── Public storage interface ──────────────────────────────────────────────

    def get(self, key: str) -> LoginAttemptState | None:
        if self._using_fallback:
            return self._memory.get(key)
        try:
            return self._redis.get(key)
        except Exception as exc:
            self._activate_fallback(exc)
            return self._memory.get(key)

    def set(self, key: str, state: LoginAttemptState, *, ttl_seconds: int) -> None:
        if self._using_fallback:
            self._memory.set(key, state, ttl_seconds=ttl_seconds)
            return
        try:
            self._redis.set(key, state, ttl_seconds=ttl_seconds)
        except Exception as exc:
            self._activate_fallback(exc)
            self._memory.set(key, state, ttl_seconds=ttl_seconds)

    def delete(self, key: str) -> None:
        if self._using_fallback:
            self._memory.delete(key)
            return
        try:
            self._redis.delete(key)
        except Exception as exc:
            self._activate_fallback(exc)
            self._memory.delete(key)

    def prune(self, *, now: float, retention_seconds: int, max_keys: int) -> None:
        if self._using_fallback:
            self._memory.prune(
                now=now,
                retention_seconds=retention_seconds,
                max_keys=min(max_keys, _FAILOVER_MAX_MEMORY_KEYS),
            )
        else:
            self._redis.prune(
                now=now, retention_seconds=retention_seconds, max_keys=max_keys
            )

    def reset_for_tests(self) -> None:
        self._redis.reset_for_tests()
        self._memory.reset_for_tests()
        with self._lock:
            self._using_fallback = False
            self._last_probe_at = 0.0

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def is_using_fallback(self) -> bool:
        return self._using_fallback

    # ── Fallback activation ───────────────────────────────────────────────────

    def _activate_fallback(self, exc: Exception) -> None:
        with self._lock:
            if not self._using_fallback:
                self._using_fallback = True
                _logger.warning(
                    "login_guard: Redis unavailable — switching to in-memory fallback. "
                    "reason=%r",
                    str(exc),
                )
            self._maybe_start_probe_thread()

    def _maybe_start_probe_thread(self) -> None:
        """Start probe thread if not already running (called under self._lock)."""
        if self._probe_thread is not None and self._probe_thread.is_alive():
            return
        t = threading.Thread(
            target=self._probe_loop, daemon=True, name="login-guard-probe"
        )
        self._probe_thread = t
        t.start()

    # ── Background probe ──────────────────────────────────────────────────────

    def _probe_loop(self) -> None:
        """Daemon thread: probes Redis until it recovers, then flushes and exits."""
        while self._using_fallback:
            time.sleep(self._probe_interval)
            if not self._using_fallback:
                break
            try:
                self._redis._client.ping()
            except Exception:
                continue  # still down — keep probing

            # Redis is back — flush and restore primary only if flush succeeds fully
            flushed_ok = self._flush_to_redis()
            if not flushed_ok:
                _logger.warning(
                    "login_guard: flush to Redis incomplete — staying on fallback."
                )
                continue

            with self._lock:
                self._using_fallback = False
                _logger.info("login_guard: Redis recovered — restored primary backend.")

    def _flush_to_redis(self) -> bool:
        """Copy all in-memory states to Redis, then clear memory.

        Returns ``True`` if all entries were flushed successfully.
        """
        with self._memory._lock:
            snapshot = dict(self._memory._state)

        flushed = 0
        failed = 0
        for key, state in snapshot.items():
            try:
                # Use a generous TTL so flushed entries outlive the reconnect window
                self._redis.set(key, state, ttl_seconds=7200)
                flushed += 1
            except Exception:
                _logger.warning("login_guard: flush failed for key (hash omitted)")
                failed += 1

        _logger.info(
            "login_guard: flush complete flushed=%d failed=%d", flushed, failed
        )
        if failed == 0:
            self._memory.reset_for_tests()
        return failed == 0
