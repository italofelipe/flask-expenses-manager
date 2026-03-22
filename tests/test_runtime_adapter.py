from __future__ import annotations

import logging

from flask import Flask

from app.http.runtime import (
    runtime_config,
    runtime_debug_or_testing,
    runtime_extension,
    runtime_logger,
    set_runtime_extension,
)


def test_runtime_config_returns_default_outside_app_context() -> None:
    assert runtime_config("MISSING_KEY", "fallback") == "fallback"
    assert runtime_debug_or_testing() is False


def test_runtime_extension_roundtrip_inside_app_context() -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True

    with app.app_context():
        assert runtime_extension("password_reset_outbox") is None
        set_runtime_extension("password_reset_outbox", [{"email": "a@test.com"}])
        assert runtime_extension("password_reset_outbox") == [{"email": "a@test.com"}]
        assert runtime_debug_or_testing() is True


def test_runtime_logger_falls_back_outside_app_context() -> None:
    logger = runtime_logger("auraxis.runtime.test")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "auraxis.runtime.test"
