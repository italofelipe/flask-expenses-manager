from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

RateLimitDegradedMode = Literal["memory_fallback", "fail_closed"]


@dataclass(frozen=True)
class RateLimitSettings:
    enabled: bool
    degraded_mode: RateLimitDegradedMode

    @property
    def fail_closed(self) -> bool:
        return self.degraded_mode == "fail_closed"


def read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_secure_runtime() -> bool:
    return not read_bool_env("FLASK_DEBUG", False) and not read_bool_env(
        "FLASK_TESTING", False
    )


def _read_explicit_bool_env(name: str) -> tuple[bool, bool]:
    raw = os.getenv(name)
    if raw is None:
        return False, False
    return raw.strip().lower() in {"1", "true", "yes", "on"}, True


def _resolve_degraded_mode() -> RateLimitDegradedMode:
    explicit_mode = str(os.getenv("RATE_LIMIT_DEGRADED_MODE", "")).strip().lower()
    if explicit_mode:
        if explicit_mode not in {"memory_fallback", "fail_closed"}:
            raise RuntimeError(
                "Invalid RATE_LIMIT_DEGRADED_MODE. Expected memory_fallback or "
                "fail_closed."
            )
        return explicit_mode  # type: ignore[return-value]

    explicit_fail_closed, has_explicit_fail_closed = _read_explicit_bool_env(
        "RATE_LIMIT_FAIL_CLOSED"
    )
    if has_explicit_fail_closed:
        return "fail_closed" if explicit_fail_closed else "memory_fallback"

    return "memory_fallback"


def build_rate_limit_settings(*, configured_backend: str) -> RateLimitSettings:
    secure_runtime = _is_secure_runtime()
    if (
        configured_backend == "redis"
        and secure_runtime
        and os.getenv("RATE_LIMIT_DEGRADED_MODE") is None
        and os.getenv("RATE_LIMIT_FAIL_CLOSED") is None
    ):
        raise RuntimeError(
            "Missing RATE_LIMIT_DEGRADED_MODE. Configure explicit degraded mode "
            "for RATE_LIMIT_BACKEND=redis in secure runtime."
        )

    return RateLimitSettings(
        enabled=read_bool_env("RATE_LIMIT_ENABLED", True),
        degraded_mode=_resolve_degraded_mode(),
    )


__all__ = [
    "RateLimitDegradedMode",
    "RateLimitSettings",
    "build_rate_limit_settings",
    "read_bool_env",
]
