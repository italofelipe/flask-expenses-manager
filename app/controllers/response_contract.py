from __future__ import annotations

from typing import Any

from flask import Response

from app.exceptions import APIError
from app.utils.api_contract import CONTRACT_HEADER, CONTRACT_V2, is_v2_contract_request
from app.utils.response_builder import error_payload, json_response, success_payload


class ResponseContractError(APIError):
    """Extensible controller-level error aligned with v1/v2 response contracts."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "BAD_REQUEST",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        legacy_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
        )
        self.legacy_payload = legacy_payload or {"message": message}


def is_v2_contract() -> bool:
    return is_v2_contract_request()


def compat_success_response(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> Response:
    payload = legacy_payload
    if is_v2_contract():
        payload = success_payload(message=message, data=data, meta=meta)
    return json_response(payload, status_code=status_code)


def compat_error_response(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> Response:
    payload = legacy_payload
    if is_v2_contract():
        payload = error_payload(message=message, code=error_code, details=details)
    return json_response(payload, status_code=status_code)


def compat_success_tuple(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    payload = legacy_payload
    if is_v2_contract():
        payload = success_payload(message=message, data=data, meta=meta)
    return payload, status_code


def compat_error_tuple(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    payload = legacy_payload
    if is_v2_contract():
        payload = error_payload(message=message, code=error_code, details=details)
    return payload, status_code


def response_from_contract_error(error: ResponseContractError) -> Response:
    return compat_error_response(
        legacy_payload=error.legacy_payload,
        status_code=error.status_code,
        message=error.message,
        error_code=error.code,
        details=error.details,
    )


__all__ = [
    "CONTRACT_HEADER",
    "CONTRACT_V2",
    "ResponseContractError",
    "is_v2_contract",
    "compat_success_response",
    "compat_error_response",
    "compat_success_tuple",
    "compat_error_tuple",
    "response_from_contract_error",
]
