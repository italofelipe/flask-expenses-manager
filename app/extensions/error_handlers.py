from flask import Flask, Response
from jwt.exceptions import PyJWTError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from app.exceptions import APIError
from app.http import (
    error_contract_from_api_error,
    error_contract_from_http_exception,
    error_contract_from_request_too_large,
    error_contract_from_unhandled_exception,
    flask_error_response,
)
from app.utils.api_contract import is_v2_contract_request
from app.utils.response_builder import (
    SENSITIVE_DATA_FIELDS,
    error_payload,
    json_response,
)


def _debug_or_testing(app: Flask) -> bool:
    return bool(app.config.get("DEBUG") or app.config.get("TESTING"))


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(PyJWTError)
    def handle_pyjwt_error(e: PyJWTError) -> Response:
        del e
        if is_v2_contract_request():
            return json_response(
                error_payload(
                    message="Token inválido",
                    code="UNAUTHORIZED",
                    details={},
                ),
                401,
            )
        return json_response({"message": "Token inválido"}, 401)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(e: RequestEntityTooLarge) -> Response:
        del e
        contract = error_contract_from_request_too_large(
            app.config.get("MAX_CONTENT_LENGTH")
        )
        return flask_error_response(
            contract,
            debug_or_testing=_debug_or_testing(app),
            sensitive_fields=SENSITIVE_DATA_FIELDS,
            response_factory=json_response,
        )

    @app.errorhandler(APIError)
    def handle_api_error(e: APIError) -> Response:
        contract = error_contract_from_api_error(e)
        return flask_error_response(
            contract,
            debug_or_testing=_debug_or_testing(app),
            sensitive_fields=SENSITIVE_DATA_FIELDS,
            response_factory=json_response,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException) -> Response:
        contract = error_contract_from_http_exception(e)
        return flask_error_response(
            contract,
            debug_or_testing=_debug_or_testing(app),
            sensitive_fields=SENSITIVE_DATA_FIELDS,
            response_factory=json_response,
        )

    @app.errorhandler(Exception)
    def handle_generic_exception(e: Exception) -> Response:
        contract = error_contract_from_unhandled_exception(e)
        app.logger.exception(
            "Unhandled exception. request_id=%s", contract.request_id or "n/a"
        )
        return flask_error_response(
            contract,
            debug_or_testing=_debug_or_testing(app),
            sensitive_fields=SENSITIVE_DATA_FIELDS,
            response_factory=json_response,
        )
