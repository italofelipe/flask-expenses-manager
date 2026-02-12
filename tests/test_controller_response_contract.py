from __future__ import annotations

from app.controllers.response_contract import (
    ResponseContractError,
    compat_error_response,
    compat_error_tuple,
    compat_success_response,
    compat_success_tuple,
    is_v2_contract,
    response_from_contract_error,
)


def test_contract_detection_and_response_compatibility(app) -> None:
    with app.test_request_context("/health"):
        assert is_v2_contract() is False
        legacy_success = compat_success_response(
            legacy_payload={"message": "ok"},
            status_code=200,
            message="ok",
            data={"id": 1},
        )
        legacy_error = compat_error_response(
            legacy_payload={"error": "boom"},
            status_code=400,
            message="boom",
            error_code="VALIDATION_ERROR",
        )

    assert legacy_success.status_code == 200
    assert legacy_success.get_json() == {"message": "ok"}
    assert legacy_error.status_code == 400
    assert legacy_error.get_json() == {"error": "boom"}

    with app.test_request_context("/health", headers={"X-API-Contract": "v2"}):
        assert is_v2_contract() is True
        v2_success = compat_success_response(
            legacy_payload={"message": "legacy"},
            status_code=200,
            message="ok",
            data={"id": 1},
        )
        v2_error = compat_error_response(
            legacy_payload={"error": "legacy"},
            status_code=400,
            message="boom",
            error_code="VALIDATION_ERROR",
            details={"field": "name"},
        )

    assert v2_success.get_json()["success"] is True
    assert v2_success.get_json()["data"] == {"id": 1}
    assert v2_error.get_json()["success"] is False
    assert v2_error.get_json()["error"]["details"] == {"field": "name"}


def test_contract_tuple_and_error_class(app) -> None:
    with app.test_request_context("/health"):
        payload, status_code = compat_success_tuple(
            legacy_payload={"message": "legacy"},
            status_code=201,
            message="created",
            data={"id": 10},
        )
        assert status_code == 201
        assert payload == {"message": "legacy"}

        error_payload, error_status = compat_error_tuple(
            legacy_payload={"error": "legacy"},
            status_code=409,
            message="conflict",
            error_code="CONFLICT",
        )
        assert error_status == 409
        assert error_payload == {"error": "legacy"}

        response = response_from_contract_error(
            ResponseContractError(
                message="Service unavailable",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                details={"component": "auth"},
                legacy_payload={"message": "Service unavailable"},
            )
        )

    assert response.status_code == 503
    assert response.get_json() == {"message": "Service unavailable"}
