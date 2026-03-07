from __future__ import annotations

from flask import Flask
from werkzeug.exceptions import NotFound

from app.exceptions import ValidationAPIError
from app.http.error_contract import (
    HTTP_ERROR_CATALOG,
    error_contract_from_api_error,
    error_contract_from_http_exception,
    error_contract_from_request_too_large,
    error_contract_from_unhandled_exception,
    serialize_error_contract,
)
from app.utils.response_builder import SENSITIVE_DATA_FIELDS


def test_http_error_catalog_exposes_expected_rest_codes() -> None:
    assert HTTP_ERROR_CATALOG[400].code == "VALIDATION_ERROR"
    assert HTTP_ERROR_CATALOG[401].code == "UNAUTHORIZED"
    assert HTTP_ERROR_CATALOG[404].code == "NOT_FOUND"
    assert HTTP_ERROR_CATALOG[500].code == "INTERNAL_ERROR"


def test_error_contract_from_api_error_keeps_status_and_details() -> None:
    contract = error_contract_from_api_error(
        ValidationAPIError(details={"field": ["required"]})
    )

    assert contract.status_code == 400
    assert contract.code == "VALIDATION_ERROR"
    assert dict(contract.details or {}) == {"field": ["required"]}


def test_error_contract_from_http_exception_maps_not_found() -> None:
    contract = error_contract_from_http_exception(NotFound("Missing"))

    assert contract.status_code == 404
    assert contract.code == "NOT_FOUND"
    assert dict(contract.details or {}) == {"http_error": "Not Found"}


def test_error_contract_from_unhandled_exception_injects_request_id(app: Flask) -> None:
    with app.test_request_context("/boom"):
        contract = error_contract_from_unhandled_exception(
            RuntimeError("boom"),
            request_id="req-123",
        )
        payload = serialize_error_contract(
            contract,
            debug_or_testing=False,
            sensitive_fields=SENSITIVE_DATA_FIELDS,
        )

    assert contract.status_code == 500
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["details"] == {"request_id": "req-123"}


def test_error_contract_from_request_too_large_exposes_max_bytes() -> None:
    contract = error_contract_from_request_too_large(1024)
    payload = serialize_error_contract(
        contract,
        debug_or_testing=False,
        sensitive_fields=SENSITIVE_DATA_FIELDS,
    )

    assert contract.status_code == 413
    assert payload["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert payload["error"]["details"] == {"max_bytes": 1024}
