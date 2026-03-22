from __future__ import annotations

from typing import Any

import pytest

from app.middleware.rate_limit_settings import build_rate_limit_settings


def test_rate_limit_requires_explicit_degraded_mode_for_redis_in_secure_runtime(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.delenv("RATE_LIMIT_DEGRADED_MODE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_FAIL_CLOSED", raising=False)

    with pytest.raises(
        RuntimeError,
        match="Missing RATE_LIMIT_DEGRADED_MODE",
    ):
        build_rate_limit_settings(configured_backend="redis")


def test_rate_limit_accepts_explicit_memory_fallback_mode(monkeypatch: Any) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.setenv("RATE_LIMIT_DEGRADED_MODE", "memory_fallback")

    settings = build_rate_limit_settings(configured_backend="redis")

    assert settings.degraded_mode == "memory_fallback"
    assert settings.fail_closed is False


def test_rate_limit_accepts_explicit_fail_closed_mode(monkeypatch: Any) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.setenv("RATE_LIMIT_DEGRADED_MODE", "fail_closed")

    settings = build_rate_limit_settings(configured_backend="redis")

    assert settings.degraded_mode == "fail_closed"
    assert settings.fail_closed is True


def test_rate_limit_supports_legacy_fail_closed_flag(monkeypatch: Any) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.delenv("RATE_LIMIT_DEGRADED_MODE", raising=False)
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED", "false")

    settings = build_rate_limit_settings(configured_backend="redis")

    assert settings.degraded_mode == "memory_fallback"
    assert settings.fail_closed is False


def test_rate_limit_keeps_relaxed_default_outside_secure_runtime(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.delenv("RATE_LIMIT_DEGRADED_MODE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_FAIL_CLOSED", raising=False)

    settings = build_rate_limit_settings(configured_backend="redis")

    assert settings.degraded_mode == "memory_fallback"
    assert settings.fail_closed is False
