from __future__ import annotations

from math import ceil
from time import time

from app.extensions.integration_metrics import increment_metric
from app.services.login_attempt_guard_backend import (
    LoginAttemptGuardBackend,
    build_login_attempt_guard_backend_from_env,
)
from app.services.login_attempt_guard_context import (
    LoginAttemptContext,
    build_login_attempt_context,
)
from app.services.login_attempt_guard_settings import (
    LoginAttemptGuardSettings,
    build_login_attempt_guard_settings,
)
from app.services.login_attempt_guard_storage import LoginAttemptState


class LoginGuardBackendUnavailableError(RuntimeError):
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason or "login guard backend unavailable"
        super().__init__(self.reason)


class LoginAttemptGuardService:
    def __init__(
        self,
        *,
        settings: LoginAttemptGuardSettings,
        backend: LoginAttemptGuardBackend,
    ) -> None:
        self._enabled = settings.enabled
        self._failure_threshold = max(1, settings.failure_threshold)
        self._known_failure_threshold = max(1, settings.known_failure_threshold)
        self._base_cooldown_seconds = max(1, settings.base_cooldown_seconds)
        self._max_cooldown_seconds = max(
            self._base_cooldown_seconds,
            settings.max_cooldown_seconds,
        )
        self._known_base_cooldown_seconds = max(
            1,
            settings.known_base_cooldown_seconds,
        )
        self._known_max_cooldown_seconds = max(
            self._known_base_cooldown_seconds,
            settings.known_max_cooldown_seconds,
        )
        self._retention_seconds = max(60, settings.retention_seconds)
        self._max_keys = max(1000, settings.max_keys)
        self._storage = backend.storage
        self.backend_name = backend.backend_name
        self.configured_backend = backend.configured_backend
        self.backend_ready = backend.backend_ready
        self.fail_closed = settings.fail_closed
        self.backend_failure_reason = backend.backend_failure_reason

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
            self._prune_storage(now)
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
            self._prune_storage(now)
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
            cooldown = min(active_base_cooldown * (2**exponent), active_max_cooldown)
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
        self._storage.set(key, state, ttl_seconds=self._state_ttl_seconds())

    def _prune_storage(self, now: float) -> None:
        self._storage.prune(
            now=now,
            retention_seconds=self._retention_seconds,
            max_keys=self._max_keys,
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


_guard: LoginAttemptGuardService | None = None


def get_login_attempt_guard() -> LoginAttemptGuardService:
    global _guard
    if _guard is None:
        backend = build_login_attempt_guard_backend_from_env()
        settings = build_login_attempt_guard_settings(
            configured_backend=backend.configured_backend,
            backend_ready=backend.backend_ready,
        )
        _guard = LoginAttemptGuardService(settings=settings, backend=backend)
    return _guard


def reset_login_attempt_guard_for_tests() -> None:
    global _guard
    if _guard is not None:
        _guard.reset_for_tests()
    _guard = None


__all__ = [
    "LoginAttemptContext",
    "LoginGuardBackendUnavailableError",
    "LoginAttemptGuardService",
    "build_login_attempt_context",
    "get_login_attempt_guard",
    "reset_login_attempt_guard_for_tests",
]
