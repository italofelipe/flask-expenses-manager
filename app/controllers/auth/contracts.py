from __future__ import annotations

from typing import Any

from flask import Response

from app.controllers.response_contract import (
    CONTRACT_HEADER,
    CONTRACT_V2,
    ResponseContractError,
    compat_error_response,
    compat_success_response,
    is_v2_contract,
    response_from_contract_error,
)

AUTH_BACKEND_UNAVAILABLE_MESSAGE = (
    "Authentication temporarily unavailable. Try again later."
)
AUTH_BACKEND_UNAVAILABLE_CODE = "AUTH_BACKEND_UNAVAILABLE"


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


def registration_ack_payload(message: str) -> dict[str, Any]:
    return {"message": message, "data": {}}


def auth_backend_unavailable_response() -> Response:
    return response_from_contract_error(
        ResponseContractError(
            message=AUTH_BACKEND_UNAVAILABLE_MESSAGE,
            code=AUTH_BACKEND_UNAVAILABLE_CODE,
            status_code=503,
            legacy_payload={"message": AUTH_BACKEND_UNAVAILABLE_MESSAGE},
        )
    )


__all__ = [
    "CONTRACT_HEADER",
    "CONTRACT_V2",
    "AUTH_BACKEND_UNAVAILABLE_MESSAGE",
    "AUTH_BACKEND_UNAVAILABLE_CODE",
    "is_v2_contract",
    "compat_success",
    "compat_error",
    "registration_ack_payload",
    "auth_backend_unavailable_response",
]
