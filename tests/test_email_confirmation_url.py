"""Tests for the confirmation URL builder + canonical fallback (#1334).

Covers:
- Fallback to canonical default when EMAIL_CONFIRMATION_FRONTEND_URL is empty
- Respect of configured env var
- Correct separator (`?` vs `&`) when base URL already has query params
"""

from __future__ import annotations

from app.application.services.email_confirmation_service import (
    _DEFAULT_CONFIRMATION_URL,
    _build_confirmation_url,
)


def test_falls_back_to_canonical_default_when_env_empty(app, monkeypatch) -> None:
    monkeypatch.setitem(app.config, "EMAIL_CONFIRMATION_FRONTEND_URL", "")
    with app.app_context():
        url = _build_confirmation_url(token="abc123")
        assert url == f"{_DEFAULT_CONFIRMATION_URL}?token=abc123"


def test_respects_configured_env_var(app, monkeypatch) -> None:
    monkeypatch.setitem(
        app.config,
        "EMAIL_CONFIRMATION_FRONTEND_URL",
        "https://staging.auraxis.com.br/confirm-email",
    )
    with app.app_context():
        url = _build_confirmation_url(token="abc123")
        assert url == "https://staging.auraxis.com.br/confirm-email?token=abc123"


def test_uses_ampersand_when_base_url_already_has_query(app, monkeypatch) -> None:
    monkeypatch.setitem(
        app.config,
        "EMAIL_CONFIRMATION_FRONTEND_URL",
        "https://app.auraxis.com.br/confirm-email?utm_source=email",
    )
    with app.app_context():
        url = _build_confirmation_url(token="xyz789")
        assert (
            url
            == "https://app.auraxis.com.br/confirm-email?utm_source=email&token=xyz789"
        )


def test_canonical_default_targets_root_confirm_email_path() -> None:
    # Guards against future regressions where someone "moves" the canonical URL
    # back under /auth/ — the Nuxt page is at /confirm-email (root).
    assert _DEFAULT_CONFIRMATION_URL == "https://app.auraxis.com.br/confirm-email"
