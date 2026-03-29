from __future__ import annotations

from typing import Any

from flask import Response

from app.controllers.response_contract import (
    ResponseContractError,
    compat_error_response,
    compat_success_response,
    response_from_contract_error,
)
from app.services.alert_service import AlertServiceError


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


def alert_service_error_response(exc: AlertServiceError) -> Response:
    return compat_error(
        legacy_payload={"error": exc.message, "details": exc.details},
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.code,
        details=exc.details,
    )


def alert_contract_error_response(error: ResponseContractError) -> Response:
    return response_from_contract_error(error)
