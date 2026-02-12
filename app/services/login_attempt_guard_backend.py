from __future__ import annotations

from dataclasses import dataclass

from app.services.login_attempt_guard_storage import (
    LoginAttemptStorage,
    build_login_attempt_storage_from_env,
)


@dataclass(frozen=True)
class LoginAttemptGuardBackend:
    storage: LoginAttemptStorage
    backend_name: str
    configured_backend: str
    backend_ready: bool
    backend_failure_reason: str | None = None


def build_login_attempt_guard_backend_from_env() -> LoginAttemptGuardBackend:
    (
        storage,
        backend_name,
        backend_ready,
        configured_backend,
        backend_failure_reason,
    ) = build_login_attempt_storage_from_env()
    return LoginAttemptGuardBackend(
        storage=storage,
        backend_name=backend_name,
        configured_backend=configured_backend,
        backend_ready=backend_ready,
        backend_failure_reason=backend_failure_reason,
    )


__all__ = [
    "LoginAttemptGuardBackend",
    "build_login_attempt_guard_backend_from_env",
]
