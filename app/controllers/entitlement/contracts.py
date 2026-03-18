from __future__ import annotations

from typing import Any

from flask import Response

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


def entitlement_error_response(
    *,
    message: str,
    code: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> Response:
    return compat_error_response(
        legacy_payload={"error": message, "details": details},
        status_code=status_code,
        message=message,
        error_code=code,
        details=details,
    )
