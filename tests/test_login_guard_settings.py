from __future__ import annotations

from typing import Any

import pytest

from app.services.login_attempt_guard_settings import build_login_attempt_guard_settings


def test_login_guard_requires_explicit_fail_policy_for_redis_in_secure_runtime(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.delenv("LOGIN_GUARD_FAIL_CLOSED", raising=False)

    with pytest.raises(
        RuntimeError,
        match="Missing LOGIN_GUARD_FAIL_CLOSED",
    ):
        build_login_attempt_guard_settings(
            configured_backend="redis",
            backend_ready=True,
        )


def test_login_guard_accepts_explicit_fail_open_policy_for_redis(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.setenv("LOGIN_GUARD_FAIL_CLOSED", "false")

    settings = build_login_attempt_guard_settings(
        configured_backend="redis",
        backend_ready=True,
    )

    assert settings.fail_closed is False


def test_login_guard_accepts_explicit_fail_closed_policy_for_redis(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.setenv("LOGIN_GUARD_FAIL_CLOSED", "true")

    settings = build_login_attempt_guard_settings(
        configured_backend="redis",
        backend_ready=True,
    )

    assert settings.fail_closed is True


def test_login_guard_keeps_relaxed_default_outside_secure_runtime(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.delenv("LOGIN_GUARD_FAIL_CLOSED", raising=False)

    settings = build_login_attempt_guard_settings(
        configured_backend="redis",
        backend_ready=True,
    )

    assert settings.fail_closed is False
