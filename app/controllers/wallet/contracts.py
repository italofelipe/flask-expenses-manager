from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.application.errors import PublicValidationError
from app.application.services.investment_application_service import (
    InvestmentApplicationError,
)
from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.application.services.wallet_application_service import WalletApplicationError
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.services.investment_operation_service import InvestmentOperationError


def compat_success(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    return compat_success_tuple(
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
) -> tuple[dict[str, Any], int]:
    return compat_error_tuple(
        legacy_payload=legacy_payload,
        status_code=status_code,
        message=message,
        error_code=error_code,
        details=details,
    )


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


def application_error_response(
    exc: InvestmentApplicationError | WalletApplicationError,
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
