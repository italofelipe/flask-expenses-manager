from __future__ import annotations

from typing import Any

from app.controllers.response_contract import (
    ResponseContractError,
    compat_error_tuple,
    compat_error_tuple_from_api_error,
    compat_success_tuple,
)
from app.exceptions import APIError


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


def api_error_tuple(
    error: APIError,
    *,
    legacy_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    return compat_error_tuple_from_api_error(
        error,
        legacy_payload=legacy_payload,
    )


def contract_error_tuple(error: ResponseContractError) -> tuple[dict[str, Any], int]:
    return compat_error_tuple(
        legacy_payload=error.legacy_payload,
        status_code=error.status_code,
        message=error.message,
        error_code=error.code,
        details=error.details,
    )
