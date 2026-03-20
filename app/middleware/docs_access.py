from __future__ import annotations

import os
from typing import Any, Final, cast

from flask import Flask, Response, abort, request

from app.auth import AuthContextError, get_active_auth_context
from app.extensions.jwt_callbacks import _jwt_error_response

_POLICY_PUBLIC: Final[str] = "public"
_POLICY_AUTHENTICATED: Final[str] = "authenticated"
_POLICY_DISABLED: Final[str] = "disabled"
_ALLOWED_POLICIES: Final[set[str]] = {
    _POLICY_PUBLIC,
    _POLICY_AUTHENTICATED,
    _POLICY_DISABLED,
}


def _is_docs_path(path: str) -> bool:
    return path.startswith("/docs")


def _default_docs_policy() -> str:
    flask_debug = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
    if flask_debug:
        return _POLICY_PUBLIC
    if _is_production_runtime():
        return _POLICY_DISABLED
    return _POLICY_AUTHENTICATED


def _is_secure_runtime() -> bool:
    is_debug = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
    is_testing = os.getenv("FLASK_TESTING", "false").strip().lower() == "true"
    return not is_debug and not is_testing


def _is_production_runtime() -> bool:
    for env_name in ("AURAXIS_ENV", "APP_ENV", "FLASK_ENV"):
        raw_value = os.getenv(env_name, "").strip().lower()
        if raw_value in {"prod", "production"}:
            return True
    return False


def _read_docs_exposure_policy() -> str:
    raw_policy = os.getenv("DOCS_EXPOSURE_POLICY", "")
    normalized_policy = raw_policy.strip().lower()
    if normalized_policy in _ALLOWED_POLICIES:
        if (
            normalized_policy == _POLICY_PUBLIC
            and _is_secure_runtime()
            and _is_production_runtime()
        ):
            raise RuntimeError(
                "Invalid DOCS_EXPOSURE_POLICY. "
                "Policy 'public' is not allowed in production runtime."
            )
        return normalized_policy
    if normalized_policy and _is_secure_runtime():
        raise RuntimeError(
            "Invalid DOCS_EXPOSURE_POLICY. "
            f"Allowed values: {sorted(_ALLOWED_POLICIES)}."
        )
    return _default_docs_policy()


def register_docs_access_guard(app: Flask) -> None:
    policy = _read_docs_exposure_policy()
    app.extensions["docs_access_policy"] = policy
    app.logger.info("docs_access_policy=%s", policy)

    @app.before_request
    def docs_access_guard() -> Response | tuple[Any, int] | None:
        if not _is_docs_path(request.path):
            return None

        if policy == _POLICY_PUBLIC:
            return None

        if policy == _POLICY_DISABLED:
            abort(404)

        try:
            get_active_auth_context()
        except AuthContextError:
            return cast(
                Response | tuple[Any, int],
                _jwt_error_response(
                    "Token inválido ou ausente",
                    code="UNAUTHORIZED",
                    status_code=401,
                ),
            )
        except Exception:
            return cast(
                Response | tuple[Any, int],
                _jwt_error_response(
                    "Token inválido ou ausente",
                    code="UNAUTHORIZED",
                    status_code=401,
                ),
            )
        return None
