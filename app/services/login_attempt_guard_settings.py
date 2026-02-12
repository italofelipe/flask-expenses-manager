from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LoginAttemptGuardSettings:
    enabled: bool
    failure_threshold: int
    known_failure_threshold: int
    base_cooldown_seconds: int
    max_cooldown_seconds: int
    known_base_cooldown_seconds: int
    known_max_cooldown_seconds: int
    retention_seconds: int
    max_keys: int
    fail_closed: bool


def read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_explicit_bool_env(name: str) -> tuple[bool, bool]:
    raw = os.getenv(name)
    if raw is None:
        return False, False
    return raw.strip().lower() in {"1", "true", "yes", "on"}, True


def read_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _is_secure_runtime() -> bool:
    return not read_bool_env("FLASK_DEBUG", False) and not read_bool_env(
        "FLASK_TESTING", False
    )


def build_login_attempt_guard_settings(
    *,
    configured_backend: str,
    backend_ready: bool,
) -> LoginAttemptGuardSettings:
    del backend_ready
    secure_runtime = _is_secure_runtime()
    default_fail_closed = configured_backend == "redis" and secure_runtime
    explicit_fail_closed, has_explicit_fail_closed = _read_explicit_bool_env(
        "LOGIN_GUARD_FAIL_CLOSED"
    )
    if (
        configured_backend == "redis"
        and secure_runtime
        and not has_explicit_fail_closed
    ):
        raise RuntimeError(
            "Missing LOGIN_GUARD_FAIL_CLOSED. Configure explicit failure policy "
            "for LOGIN_GUARD_BACKEND=redis in secure runtime."
        )
    fail_closed = (
        explicit_fail_closed if has_explicit_fail_closed else default_fail_closed
    )
    return LoginAttemptGuardSettings(
        enabled=read_bool_env("LOGIN_GUARD_ENABLED", True),
        failure_threshold=read_positive_int_env("LOGIN_GUARD_FAILURE_THRESHOLD", 5),
        known_failure_threshold=read_positive_int_env(
            "LOGIN_GUARD_KNOWN_FAILURE_THRESHOLD",
            read_positive_int_env("LOGIN_GUARD_FAILURE_THRESHOLD", 5),
        ),
        base_cooldown_seconds=read_positive_int_env(
            "LOGIN_GUARD_BASE_COOLDOWN_SECONDS", 30
        ),
        max_cooldown_seconds=read_positive_int_env(
            "LOGIN_GUARD_MAX_COOLDOWN_SECONDS", 900
        ),
        known_base_cooldown_seconds=read_positive_int_env(
            "LOGIN_GUARD_KNOWN_BASE_COOLDOWN_SECONDS",
            read_positive_int_env("LOGIN_GUARD_BASE_COOLDOWN_SECONDS", 30),
        ),
        known_max_cooldown_seconds=read_positive_int_env(
            "LOGIN_GUARD_KNOWN_MAX_COOLDOWN_SECONDS",
            read_positive_int_env("LOGIN_GUARD_MAX_COOLDOWN_SECONDS", 900),
        ),
        retention_seconds=read_positive_int_env("LOGIN_GUARD_RETENTION_SECONDS", 3600),
        max_keys=read_positive_int_env("LOGIN_GUARD_MAX_KEYS", 20000),
        fail_closed=fail_closed,
    )


__all__ = [
    "LoginAttemptGuardSettings",
    "read_bool_env",
    "read_positive_int_env",
    "build_login_attempt_guard_settings",
]
