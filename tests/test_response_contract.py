from flask import Flask
from werkzeug.exceptions import NotFound

from app.exceptions import ValidationAPIError
from app.extensions.error_handlers import register_error_handlers
from app.utils.response_builder import error_payload, success_payload


def test_success_payload_contract() -> None:
    payload = success_payload("ok", data={"id": 1}, meta={"request_id": "abc"})

    assert payload["success"] is True
    assert payload["message"] == "ok"
    assert payload["data"] == {"id": 1}
    assert payload["meta"] == {"request_id": "abc"}


def test_error_payload_contract() -> None:
    payload = error_payload(
        "validation error",
        code="VALIDATION_ERROR",
        details={"email": ["invalid"]},
    )

    assert payload["success"] is False
    assert payload["message"] == "validation error"
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"] == {"email": ["invalid"]}


def test_api_error_handler_uses_standard_contract() -> None:
    app = Flask(__name__)
    register_error_handlers(app)

    @app.route("/validation-error")
    def validation_error() -> None:
        raise ValidationAPIError(details={"field": ["required"]})

    client = app.test_client()
    response = client.get("/validation-error")
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["details"] == {"field": ["required"]}


def test_http_exception_handler_uses_standard_contract() -> None:
    app = Flask(__name__)
    register_error_handlers(app)

    @app.route("/missing")
    def missing() -> None:
        raise NotFound("Not found message")

    client = app.test_client()
    response = client.get("/missing")
    data = response.get_json()

    assert response.status_code == 404
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"
    assert data["error"]["details"] == {"http_error": "Not Found"}


def test_generic_exception_handler_uses_standard_contract() -> None:
    app = Flask(__name__)
    register_error_handlers(app)

    @app.route("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    client = app.test_client()
    response = client.get("/boom")
    data = response.get_json()

    assert response.status_code == 500
    assert data["success"] is False
    assert data["error"]["code"] == "INTERNAL_ERROR"
