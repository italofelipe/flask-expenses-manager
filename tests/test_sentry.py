"""Unit tests for app/extensions/sentry.py.

All tests mock sentry_sdk.init to avoid real network calls and assert the
correct initialisation behaviour under different environment configurations.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_sentry():
    """Force a fresh import of the sentry extension module."""
    import app.extensions.sentry as mod

    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sentry_not_initialised_when_dsn_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_sentry() must be a no-op when SENTRY_DSN is not set."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        mock_init.assert_not_called()


def test_sentry_not_initialised_when_dsn_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_sentry() must be a no-op when SENTRY_DSN is an empty string."""
    monkeypatch.setenv("SENTRY_DSN", "")

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        mock_init.assert_not_called()


def test_sentry_not_initialised_when_dsn_is_whitespace_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_sentry() must be a no-op when SENTRY_DSN contains only whitespace."""
    monkeypatch.setenv("SENTRY_DSN", "   ")

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        mock_init.assert_not_called()


def test_sentry_initialised_when_dsn_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_sentry() must call sentry_sdk.init exactly once when SENTRY_DSN is set."""
    fake_dsn = "https://public@sentry.example.io/1"
    monkeypatch.setenv("SENTRY_DSN", fake_dsn)
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "test")
    monkeypatch.setenv("SENTRY_TRACES_RATE", "0.5")
    monkeypatch.setenv("SENTRY_PROFILES_RATE", "0.2")

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        mock_init.assert_called_once()


def test_sentry_init_receives_correct_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """sentry_sdk.init must be called with the exact DSN from the environment."""
    fake_dsn = "https://public@sentry.example.io/42"
    monkeypatch.setenv("SENTRY_DSN", fake_dsn)

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        _, kwargs = mock_init.call_args
        assert kwargs.get("dsn") == fake_dsn


def test_sentry_init_send_default_pii_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_default_pii must always be False to comply with LGPD."""
    monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.example.io/99")

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        _, kwargs = mock_init.call_args
        assert kwargs.get("send_default_pii") is False


def test_sentry_init_flask_integration_included(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FlaskIntegration must be present in the integrations list."""
    from sentry_sdk.integrations.flask import FlaskIntegration

    monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.example.io/77")

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        _, kwargs = mock_init.call_args
        integrations = kwargs.get("integrations", [])
        types = [type(i) for i in integrations]
        assert FlaskIntegration in types


def test_sentry_init_sqlalchemy_integration_included(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SqlalchemyIntegration must be present in the integrations list."""
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.example.io/88")

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        _, kwargs = mock_init.call_args
        integrations = kwargs.get("integrations", [])
        types = [type(i) for i in integrations]
        assert SqlalchemyIntegration in types


def test_sentry_init_traces_sample_rate_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """traces_sample_rate must reflect SENTRY_TRACES_RATE env var."""
    monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.example.io/55")
    monkeypatch.setenv("SENTRY_TRACES_RATE", "0.25")

    with patch("sentry_sdk.init") as mock_init:
        mod = _reload_sentry()
        mod.init_sentry()
        _, kwargs = mock_init.call_args
        assert kwargs.get("traces_sample_rate") == pytest.approx(0.25)
