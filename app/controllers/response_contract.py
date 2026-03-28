from __future__ import annotations

from typing import Any

from flask import Response

from app.exceptions import APIError
from app.http import (
    ErrorContract,
    flask_error_response,
    runtime_debug_or_testing,
    serialize_error_contract,
)
from app.utils.api_contract import (
    CONTRACT_HEADER,
    CONTRACT_V2,
    CONTRACT_V3,
    is_v2_contract_request,
    is_v3_contract_request,
)
from app.utils.response_builder import (
    SENSITIVE_DATA_FIELDS,
    json_response,
    success_payload,
)

DEFAULT_DEPRECATION_SUNSET = "Tue, 30 Jun 2026 23:59:59 GMT"


def _debug_or_testing() -> bool:
    return runtime_debug_or_testing()


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


def is_v3_contract() -> bool:
    return is_v3_contract_request()


def is_standard_contract() -> bool:
    return is_v2_contract() or is_v3_contract()


def compat_success_response(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> Response:
    payload = legacy_payload
    if is_standard_contract():
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
    if is_standard_contract():
        return flask_error_response(
            ErrorContract(
                message=message,
                code=error_code,
                status_code=status_code,
                details=details,
            ),
            debug_or_testing=_debug_or_testing(),
            sensitive_fields=SENSITIVE_DATA_FIELDS,
            response_factory=json_response,
        )
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
    if is_standard_contract():
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
    if is_standard_contract():
        payload = serialize_error_contract(
            ErrorContract(
                message=message,
                code=error_code,
                status_code=status_code,
                details=details,
            ),
            debug_or_testing=_debug_or_testing(),
            sensitive_fields=SENSITIVE_DATA_FIELDS,
        )
    return payload, status_code


def compat_error_tuple_from_api_error(
    error: APIError,
    *,
    legacy_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    return compat_error_tuple(
        legacy_payload=legacy_payload or {"error": error.message},
        status_code=error.status_code,
        message=error.message,
        error_code=error.code,
        details=error.details,
    )


def apply_deprecation_headers(
    response: Response,
    *,
    successor_endpoint: str | None = None,
    successor_method: str | None = None,
    successor_contract: str | None = None,
    successor_field: str | None = None,
    warning: str | None = None,
    sunset: str = DEFAULT_DEPRECATION_SUNSET,
) -> Response:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = sunset
    if successor_endpoint is not None:
        response.headers["X-Auraxis-Successor-Endpoint"] = successor_endpoint
    if successor_method is not None:
        response.headers["X-Auraxis-Successor-Method"] = successor_method
    if successor_contract is not None:
        response.headers["X-Auraxis-Successor-Contract"] = successor_contract
    if successor_field is not None:
        response.headers["X-Auraxis-Successor-Field"] = successor_field
    if warning is not None:
        response.headers["Warning"] = warning
    return response


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
    "CONTRACT_V3",
    "ResponseContractError",
    "is_standard_contract",
    "is_v2_contract",
    "is_v3_contract",
    "compat_success_response",
    "compat_error_response",
    "compat_success_tuple",
    "compat_error_tuple",
    "compat_error_tuple_from_api_error",
    "apply_deprecation_headers",
    "response_from_contract_error",
]
