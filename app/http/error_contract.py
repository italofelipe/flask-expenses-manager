from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from flask import Response
from werkzeug.exceptions import HTTPException

from app.exceptions import APIError
from app.http.request_context import current_request_id


@dataclass(frozen=True)
class ErrorCatalogEntry:
    code: str
    status_code: int
    default_message: str


@dataclass(frozen=True)
class ErrorContract:
    message: str
    code: str
    status_code: int
    details: Mapping[str, Any] | None = None
    request_id: str | None = None
    docs_url: str | None = None


HTTP_ERROR_CATALOG: dict[int, ErrorCatalogEntry] = {
    400: ErrorCatalogEntry(
        code="VALIDATION_ERROR",
        status_code=400,
        default_message="Validation error",
    ),
    401: ErrorCatalogEntry(
        code="UNAUTHORIZED",
        status_code=401,
        default_message="Unauthorized",
    ),
    403: ErrorCatalogEntry(
        code="FORBIDDEN",
        status_code=403,
        default_message="Forbidden",
    ),
    404: ErrorCatalogEntry(
        code="NOT_FOUND",
        status_code=404,
        default_message="Not found",
    ),
    409: ErrorCatalogEntry(
        code="CONFLICT",
        status_code=409,
        default_message="Conflict",
    ),
    413: ErrorCatalogEntry(
        code="PAYLOAD_TOO_LARGE",
        status_code=413,
        default_message="Request body is too large.",
    ),
    422: ErrorCatalogEntry(
        code="UNPROCESSABLE_ENTITY",
        status_code=422,
        default_message="Unprocessable entity",
    ),
    500: ErrorCatalogEntry(
        code="INTERNAL_ERROR",
        status_code=500,
        default_message="An unexpected error occurred.",
    ),
}


def _sanitize_value(value: Any, *, sensitive_fields: set[str]) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in sensitive_fields:
                continue
            sanitized[key] = _sanitize_value(item, sensitive_fields=sensitive_fields)
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize_value(item, sensitive_fields=sensitive_fields) for item in value
        ]
    return value


def serialize_error_contract(
    contract: ErrorContract,
    *,
    debug_or_testing: bool,
    sensitive_fields: set[str],
) -> dict[str, Any]:
    if contract.code == "INTERNAL_ERROR" and not debug_or_testing:
        request_id = contract.request_id or current_request_id(default="")
        sanitized_details: dict[str, Any] = (
            {"request_id": request_id} if request_id else {}
        )
    else:
        details = dict(contract.details or {})
        sanitized_details = _sanitize_value(details, sensitive_fields=sensitive_fields)

    error_payload: dict[str, Any] = {
        "code": contract.code,
        "details": sanitized_details,
    }
    if contract.docs_url:
        error_payload["docs_url"] = contract.docs_url

    return {
        "success": False,
        "message": contract.message,
        "error": error_payload,
    }


def error_contract_from_api_error(error: APIError) -> ErrorContract:
    return ErrorContract(
        message=error.message,
        code=error.code,
        status_code=error.status_code,
        details=error.details,
    )


def error_contract_from_http_exception(error: HTTPException) -> ErrorContract:
    status_code = error.code if error.code is not None else 500
    catalog_entry = HTTP_ERROR_CATALOG.get(
        status_code,
        ErrorCatalogEntry(
            code="HTTP_ERROR",
            status_code=status_code,
            default_message="HTTP error",
        ),
    )
    message = error.description or catalog_entry.default_message
    return ErrorContract(
        message=message,
        code=catalog_entry.code,
        status_code=status_code,
        details={"http_error": error.name},
    )


def error_contract_from_unhandled_exception(
    error: Exception, *, request_id: str | None = None
) -> ErrorContract:
    del error
    catalog_entry = HTTP_ERROR_CATALOG[500]
    return ErrorContract(
        message=catalog_entry.default_message,
        code=catalog_entry.code,
        status_code=catalog_entry.status_code,
        request_id=request_id or current_request_id(default=""),
    )


def error_contract_from_request_too_large(max_bytes: int | None) -> ErrorContract:
    catalog_entry = HTTP_ERROR_CATALOG[413]
    return ErrorContract(
        message=catalog_entry.default_message,
        code=catalog_entry.code,
        status_code=catalog_entry.status_code,
        details={"max_bytes": max_bytes},
    )


def flask_error_response(
    contract: ErrorContract,
    *,
    debug_or_testing: bool,
    sensitive_fields: set[str],
    response_factory: Callable[[dict[str, Any], int], Response],
) -> Response:
    payload = serialize_error_contract(
        contract,
        debug_or_testing=debug_or_testing,
        sensitive_fields=sensitive_fields,
    )
    return response_factory(payload, contract.status_code)


__all__ = [
    "ErrorCatalogEntry",
    "ErrorContract",
    "HTTP_ERROR_CATALOG",
    "error_contract_from_api_error",
    "error_contract_from_http_exception",
    "error_contract_from_request_too_large",
    "error_contract_from_unhandled_exception",
    "flask_error_response",
    "serialize_error_contract",
]
