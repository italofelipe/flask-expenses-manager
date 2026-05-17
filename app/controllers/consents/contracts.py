"""Shared response helpers for the consents blueprint."""

from __future__ import annotations

from typing import Any

from flask import Response

from app.controllers.response_contract import (
    compat_error_response,
    compat_success_response,
)


def consent_success(
    *,
    message: str,
    data: Any,
    status_code: int = 200,
) -> Response:
    return compat_success_response(
        legacy_payload={"message": message, "data": data},
        status_code=status_code,
        message=message,
        data=data,
    )


def consent_error(
    *,
    message: str,
    status_code: int,
    error_code: str,
) -> Response:
    return compat_error_response(
        legacy_payload={"message": message},
        status_code=status_code,
        message=message,
        error_code=error_code,
    )
