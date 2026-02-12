from __future__ import annotations

import importlib

import config as config_module


def _reload_config_module():
    return importlib.reload(config_module)


def test_config_debug_defaults_to_false_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    module = _reload_config_module()
    assert module.Config.DEBUG is False


def test_validate_security_configuration_rejects_debug_in_production(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SECURITY_ENFORCE_STRONG_SECRETS", "true")
    monkeypatch.setenv("AURAXIS_ENV", "production")
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("FLASK_TESTING", "false")
    module = _reload_config_module()

    try:
        module.validate_security_configuration()
        assert False, "Expected RuntimeError for debug mode in production."
    except RuntimeError as exc:
        assert "FLASK_DEBUG must be false in production" in str(exc)


def test_validate_security_configuration_allows_debug_outside_production(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SECURITY_ENFORCE_STRONG_SECRETS", "true")
    monkeypatch.setenv("AURAXIS_ENV", "dev")
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("FLASK_TESTING", "false")
    module = _reload_config_module()

    module.validate_security_configuration()


def test_validate_security_configuration_rejects_weak_secrets_in_secure_runtime(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SECURITY_ENFORCE_STRONG_SECRETS", "true")
    monkeypatch.setenv("AURAXIS_ENV", "production")
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.setenv("SECRET_KEY", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-key")
    module = _reload_config_module()

    try:
        module.validate_security_configuration()
        assert False, "Expected RuntimeError for weak secrets."
    except RuntimeError as exc:
        assert "Weak/invalid secrets" in str(exc)


def test_validate_security_configuration_can_be_disabled_with_flag(monkeypatch) -> None:
    monkeypatch.setenv("SECURITY_ENFORCE_STRONG_SECRETS", "false")
    monkeypatch.setenv("AURAXIS_ENV", "production")
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.setenv("SECRET_KEY", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-key")
    module = _reload_config_module()

    module.validate_security_configuration()
