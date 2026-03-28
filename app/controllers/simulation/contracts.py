from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from flask import Response

from app.application.services.installment_vs_cash_application_service import (
    InstallmentVsCashApplicationError,
)
from app.application.services.simulation_application_service import (
    SimulationApplicationError,
)
from app.controllers.response_contract import (
    apply_deprecation_headers,
    compat_error_response,
    compat_success_response,
)


def compat_success(
    *,
    legacy_payload: Mapping[str, object],
    status_code: int,
    message: str,
    data: Mapping[str, object],
    meta: Mapping[str, object] | None = None,
) -> Response:
    return compat_success_response(
        legacy_payload=cast(dict[str, Any], dict(legacy_payload)),
        status_code=status_code,
        message=message,
        data=cast(dict[str, Any], dict(data)),
        meta=None if meta is None else cast(dict[str, Any], dict(meta)),
    )


def compat_success_deprecated(
    *,
    legacy_payload: Mapping[str, object],
    status_code: int,
    message: str,
    data: Mapping[str, object],
    meta: Mapping[str, object] | None = None,
    successor_endpoint: str | None = None,
    successor_method: str | None = None,
    successor_field: str | None = None,
    warning: str | None = None,
) -> Response:
    response = compat_success_response(
        legacy_payload=cast(dict[str, Any], dict(legacy_payload)),
        status_code=status_code,
        message=message,
        data=cast(dict[str, Any], dict(data)),
        meta=None if meta is None else cast(dict[str, Any], dict(meta)),
    )
    return apply_deprecation_headers(
        response,
        successor_endpoint=successor_endpoint,
        successor_method=successor_method,
        successor_field=successor_field,
        warning=warning,
    )


def simulation_application_error_response(
    exc: SimulationApplicationError,
) -> Response:
    return compat_error_response(
        legacy_payload={"error": exc.message, "details": exc.details},
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.code,
        details=exc.details,
    )


def installment_vs_cash_application_error_response(
    exc: InstallmentVsCashApplicationError,
) -> Response:
    return compat_error_response(
        legacy_payload={"error": exc.message, "details": exc.details},
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.code,
        details=exc.details,
    )
