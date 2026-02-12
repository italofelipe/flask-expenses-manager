from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from math import ceil
from time import time

from app.extensions.integration_metrics import increment_metric
from app.services.login_attempt_guard_storage import (
    LoginAttemptState,
    LoginAttemptStorage,
    build_login_attempt_storage_from_env,
)


@dataclass(frozen=True)
class LoginAttemptContext:
    principal: str
    client_ip: str
    user_agent: str
    known_principal: bool = False

    def key(self) -> str:
        raw = f"{self.principal}|{self.client_ip}|{self.user_agent}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LoginGuardBackendUnavailableError(RuntimeError):
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason or "login guard backend unavailable"
        super().__init__(self.reason)


class LoginAttemptGuardService:
    def __init__(
        self,
        *,
        enabled: bool,
        failure_threshold: int,
        known_failure_threshold: int,
        base_cooldown_seconds: int,
        max_cooldown_seconds: int,
        known_base_cooldown_seconds: int,
        known_max_cooldown_seconds: int,
        retention_seconds: int,
        max_keys: int,
        storage: LoginAttemptStorage,
        backend_name: str,
        configured_backend: str,
        backend_ready: bool,
        fail_closed: bool,
        backend_failure_reason: str | None = None,
    ) -> None:
        self._enabled = enabled
        self._failure_threshold = max(1, failure_threshold)
        self._known_failure_threshold = max(1, known_failure_threshold)
        self._base_cooldown_seconds = max(1, base_cooldown_seconds)
        self._max_cooldown_seconds = max(
            self._base_cooldown_seconds,
            max_cooldown_seconds,
        )
        self._known_base_cooldown_seconds = max(1, known_base_cooldown_seconds)
        self._known_max_cooldown_seconds = max(
            self._known_base_cooldown_seconds,
            known_max_cooldown_seconds,
        )
        self._retention_seconds = max(60, retention_seconds)
        self._max_keys = max(1000, max_keys)
        self._storage = storage
        self.backend_name = backend_name
        self.configured_backend = configured_backend
        self.backend_ready = backend_ready
        self.fail_closed = fail_closed
        self.backend_failure_reason = backend_failure_reason

    @property
    def enabled(self) -> bool:
        return self._enabled

    def check(self, context: LoginAttemptContext) -> tuple[bool, int]:
        if not self._enabled:
            return True, 0
        self._raise_if_backend_unavailable()
        now = time()
        key = context.key()
        try:
            self._storage.prune(
                now=now,
                retention_seconds=self._retention_seconds,
                max_keys=self._max_keys,
            )
            state = self._storage.get(key)
        except Exception as exc:
            return self._handle_backend_error_for_check(exc)

        if state is None:
            increment_metric("login_guard.check.allowed")
            increment_metric("login_guard.check.allowed.no_state")
            return True, 0
        if state.blocked_until <= now:
            increment_metric("login_guard.check.allowed")
            increment_metric("login_guard.check.allowed.expired_block")
            return True, 0
        retry_after = int(ceil(state.blocked_until - now))
        increment_metric("login_guard.check.blocked")
        suffix = "known" if context.known_principal else "unknown"
        increment_metric(f"login_guard.check.blocked.{suffix}")
        return False, max(1, retry_after)

    def register_failure(self, context: LoginAttemptContext) -> int:
        if not self._enabled:
            return 0
        self._raise_if_backend_unavailable()
        now = time()
        key = context.key()
        try:
            self._storage.prune(
                now=now,
                retention_seconds=self._retention_seconds,
                max_keys=self._max_keys,
            )
            state = self._storage.get(key) or LoginAttemptState()
            if state.blocked_until > now:
                state.updated_at = now
                self._persist_state(key, state)
                increment_metric("login_guard.failure.while_blocked")
                return int(ceil(state.blocked_until - now))

            state.failures += 1
            state.updated_at = now
            increment_metric("login_guard.failure")
            suffix = "known" if context.known_principal else "unknown"
            increment_metric(f"login_guard.failure.{suffix}")

            (
                active_failure_threshold,
                active_base_cooldown,
                active_max_cooldown,
            ) = self._resolve_policy(context)

            if state.failures < active_failure_threshold:
                self._persist_state(key, state)
                return 0

            exponent = state.failures - active_failure_threshold
            cooldown = min(
                active_base_cooldown * (2**exponent),
                active_max_cooldown,
            )
            state.blocked_until = now + cooldown
            self._persist_state(key, state)
            increment_metric("login_guard.cooldown.started")
            increment_metric(f"login_guard.cooldown.started.{suffix}")
            return int(cooldown)
        except Exception as exc:
            return self._handle_backend_error_for_mutation(exc)

    def register_success(self, context: LoginAttemptContext) -> None:
        if not self._enabled:
            return
        self._raise_if_backend_unavailable()
        key = context.key()
        try:
            self._storage.delete(key)
        except Exception as exc:
            self._handle_backend_error_for_mutation(exc)
            return
        increment_metric("login_guard.success")

    def _resolve_policy(self, context: LoginAttemptContext) -> tuple[int, int, int]:
        if context.known_principal:
            return (
                self._known_failure_threshold,
                self._known_base_cooldown_seconds,
                self._known_max_cooldown_seconds,
            )
        return (
            self._failure_threshold,
            self._base_cooldown_seconds,
            self._max_cooldown_seconds,
        )

    def _state_ttl_seconds(self) -> int:
        max_cooldown = max(
            self._max_cooldown_seconds,
            self._known_max_cooldown_seconds,
        )
        return max(self._retention_seconds, 60) + max_cooldown

    def _persist_state(self, key: str, state: LoginAttemptState) -> None:
        self._storage.set(
            key,
            state,
            ttl_seconds=self._state_ttl_seconds(),
        )

    def _is_fail_closed_active(self) -> bool:
        return (
            self.fail_closed
            and self.configured_backend == "redis"
            and not self.backend_ready
        )

    def _raise_if_backend_unavailable(self) -> None:
        if not self._is_fail_closed_active():
            return
        increment_metric("login_guard.backend_unavailable")
        raise LoginGuardBackendUnavailableError(self.backend_failure_reason)

    def _handle_backend_error_for_check(self, exc: Exception) -> tuple[bool, int]:
        increment_metric("login_guard.backend_error")
        if self.fail_closed and self.configured_backend == "redis":
            raise LoginGuardBackendUnavailableError(
                "login guard backend error"
            ) from exc
        return True, 0

    def _handle_backend_error_for_mutation(self, exc: Exception) -> int:
        increment_metric("login_guard.backend_error")
        if self.fail_closed and self.configured_backend == "redis":
            raise LoginGuardBackendUnavailableError(
                "login guard backend error"
            ) from exc
        return 0

    def reset_for_tests(self) -> None:
        self._storage.reset_for_tests()


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _resolve_client_ip(
    *,
    remote_addr: str | None,
    forwarded_for: str | None,
    real_ip: str | None,
) -> str:
    trust_proxy = _read_bool_env("LOGIN_GUARD_TRUST_PROXY_HEADERS", False)
    if trust_proxy:
        forwarded = str(forwarded_for or "").strip()
        if forwarded:
            first_hop = forwarded.split(",")[0].strip()
            if first_hop:
                return first_hop
        real = str(real_ip or "").strip()
        if real:
            return real
    return str(remote_addr or "unknown")


def build_login_attempt_context(
    *,
    principal: str,
    remote_addr: str | None,
    user_agent: str | None,
    forwarded_for: str | None = None,
    real_ip: str | None = None,
    known_principal: bool = False,
) -> LoginAttemptContext:
    normalized_principal = principal.strip().lower()
    normalized_agent = str(user_agent or "").strip()[:512]
    client_ip = _resolve_client_ip(
        remote_addr=remote_addr,
        forwarded_for=forwarded_for,
        real_ip=real_ip,
    )
    return LoginAttemptContext(
        principal=normalized_principal,
        client_ip=client_ip,
        user_agent=normalized_agent,
        known_principal=known_principal,
    )


_guard: LoginAttemptGuardService | None = None


def get_login_attempt_guard() -> LoginAttemptGuardService:
    global _guard
    if _guard is None:
        (
            storage,
            backend_name,
            backend_ready,
            configured_backend,
            backend_failure_reason,
        ) = build_login_attempt_storage_from_env()
        default_fail_closed = (
            configured_backend == "redis"
            and not _read_bool_env("FLASK_DEBUG", False)
            and not _read_bool_env("FLASK_TESTING", False)
        )
        fail_closed = _read_bool_env("LOGIN_GUARD_FAIL_CLOSED", default_fail_closed)
        _guard = LoginAttemptGuardService(
            enabled=_read_bool_env("LOGIN_GUARD_ENABLED", True),
            failure_threshold=_read_int_env("LOGIN_GUARD_FAILURE_THRESHOLD", 5),
            known_failure_threshold=_read_int_env(
                "LOGIN_GUARD_KNOWN_FAILURE_THRESHOLD",
                _read_int_env("LOGIN_GUARD_FAILURE_THRESHOLD", 5),
            ),
            base_cooldown_seconds=_read_int_env(
                "LOGIN_GUARD_BASE_COOLDOWN_SECONDS",
                30,
            ),
            max_cooldown_seconds=_read_int_env(
                "LOGIN_GUARD_MAX_COOLDOWN_SECONDS",
                900,
            ),
            known_base_cooldown_seconds=_read_int_env(
                "LOGIN_GUARD_KNOWN_BASE_COOLDOWN_SECONDS",
                _read_int_env(
                    "LOGIN_GUARD_BASE_COOLDOWN_SECONDS",
                    30,
                ),
            ),
            known_max_cooldown_seconds=_read_int_env(
                "LOGIN_GUARD_KNOWN_MAX_COOLDOWN_SECONDS",
                _read_int_env(
                    "LOGIN_GUARD_MAX_COOLDOWN_SECONDS",
                    900,
                ),
            ),
            retention_seconds=_read_int_env(
                "LOGIN_GUARD_RETENTION_SECONDS",
                3600,
            ),
            max_keys=_read_int_env("LOGIN_GUARD_MAX_KEYS", 20000),
            storage=storage,
            backend_name=backend_name,
            configured_backend=configured_backend,
            backend_ready=backend_ready,
            fail_closed=fail_closed,
            backend_failure_reason=backend_failure_reason,
        )
    return _guard


def reset_login_attempt_guard_for_tests() -> None:
    global _guard
    if _guard is not None:
        _guard.reset_for_tests()
    _guard = None
