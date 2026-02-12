from __future__ import annotations

from datetime import date, datetime
from typing import Any

from flask import request

from app.application.errors import PublicValidationError
from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.services.investment_operation_service import InvestmentOperationError
from app.utils.response_builder import error_payload, success_payload

CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"


def is_v2_contract() -> bool:
    header_value = str(request.headers.get(CONTRACT_HEADER, "")).strip().lower()
    return header_value == CONTRACT_V2


def compat_success(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    if is_v2_contract():
        return success_payload(message=message, data=data, meta=meta), status_code
    return legacy_payload, status_code


def compat_error(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    if is_v2_contract():
        return (
            error_payload(
                message=message,
                code=error_code,
                details=details,
            ),
            status_code,
        )
    return legacy_payload, status_code


def operation_error_response(
    exc: InvestmentOperationError,
) -> tuple[dict[str, Any], int]:
    return compat_error(
        legacy_payload={"error": exc.message, "details": exc.details},
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.code,
        details=exc.details,
    )


def parse_optional_query_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise PublicValidationError(
            f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD."
        )


def validation_error_response(
    *,
    exc: Exception,
    fallback_message: str,
) -> tuple[dict[str, Any], int]:
    mapped_error = map_validation_exception(exc, fallback_message=fallback_message)
    return compat_error(
        legacy_payload={"error": mapped_error.message},
        status_code=mapped_error.status_code,
        message=mapped_error.message,
        error_code=mapped_error.code,
        details=mapped_error.details,
    )
