from __future__ import annotations

from flask import Response

from app.services.login_attempt_guard_service import (
    LoginAttemptContext,
    LoginAttemptGuardService,
    LoginGuardBackendUnavailableError,
)

from .contracts import auth_backend_unavailable_response


def guard_login_check(
    *,
    login_guard: LoginAttemptGuardService,
    login_context: LoginAttemptContext,
) -> tuple[bool, int] | Response:
    try:
        return login_guard.check(login_context)
    except LoginGuardBackendUnavailableError:
        return auth_backend_unavailable_response()


def guard_register_failure(
    *,
    login_guard: LoginAttemptGuardService,
    login_context: LoginAttemptContext,
) -> Response | None:
    try:
        login_guard.register_failure(login_context)
    except LoginGuardBackendUnavailableError:
        return auth_backend_unavailable_response()
    return None


def guard_register_success(
    *,
    login_guard: LoginAttemptGuardService,
    login_context: LoginAttemptContext,
) -> Response | None:
    try:
        login_guard.register_success(login_context)
    except LoginGuardBackendUnavailableError:
        return auth_backend_unavailable_response()
    return None
