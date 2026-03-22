from __future__ import annotations

import logging
from typing import Any

from flask import current_app, has_app_context


def runtime_config(name: str, default: Any = None) -> Any:
    if not has_app_context():
        return default
    return current_app.config.get(name, default)


def runtime_extension(name: str, default: Any = None) -> Any:
    if not has_app_context():
        return default
    return current_app.extensions.get(name, default)


def set_runtime_extension(name: str, value: Any) -> Any:
    if not has_app_context():
        return value
    current_app.extensions[name] = value
    return value


def runtime_logger(name: str = "auraxis.runtime") -> logging.Logger:
    if has_app_context():
        return current_app.logger
    return logging.getLogger(name)


def runtime_debug_or_testing() -> bool:
    return bool(runtime_config("DEBUG", False) or runtime_config("TESTING", False))


__all__ = [
    "runtime_config",
    "runtime_debug_or_testing",
    "runtime_extension",
    "runtime_logger",
    "set_runtime_extension",
]
