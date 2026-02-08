from flask import Flask, Response
from werkzeug.exceptions import HTTPException

from app.exceptions import APIError
from app.utils.response_builder import error_payload, json_response


def _http_status_to_error_code(status_code: int) -> str:
    mapping = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
    }
    return mapping.get(status_code, "HTTP_ERROR")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)  # type: ignore[misc]
    def handle_api_error(e: APIError) -> Response:
        payload = error_payload(
            message=e.message,
            code=e.code,
            details=e.details,
        )
        return json_response(payload, status_code=e.status_code)

    @app.errorhandler(HTTPException)  # type: ignore[misc]
    def handle_http_exception(e: HTTPException) -> Response:
        status_code = e.code if e.code is not None else 500
        payload = error_payload(
            message=e.description,
            code=_http_status_to_error_code(status_code),
            details={"http_error": e.name},
        )
        return json_response(payload, status_code=status_code)

    @app.errorhandler(Exception)  # type: ignore[misc]
    def handle_generic_exception(e: Exception) -> Response:
        app.logger.error(f"Unhandled Exception: {str(e)}")
        payload = error_payload(
            message="An unexpected error occurred.",
            code="INTERNAL_ERROR",
            details={},
        )
        return json_response(payload, status_code=500)
