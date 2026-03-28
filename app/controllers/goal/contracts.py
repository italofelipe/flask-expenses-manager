from __future__ import annotations

from typing import Any

from flask import Response

from app.application.services.goal_application_service import GoalApplicationError
from app.controllers.response_contract import (
    compat_error_response,
    compat_success_response,
)


def compat_success(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> Response:
    return compat_success_response(
        legacy_payload=legacy_payload,
        status_code=status_code,
        message=message,
        data=data,
        meta=meta,
    )


def compat_error(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> Response:
    return compat_error_response(
        legacy_payload=legacy_payload,
        status_code=status_code,
        message=message,
        error_code=error_code,
        details=details,
    )


def goal_application_error_response(exc: GoalApplicationError) -> Response:
    return compat_error(
        legacy_payload={"error": exc.message, "details": exc.details},
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.code,
        details=exc.details,
    )
