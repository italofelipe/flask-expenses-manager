from flask import Flask, Response, g
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

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
    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(e: RequestEntityTooLarge) -> Response:
        payload = error_payload(
            message="Request body is too large.",
            code="PAYLOAD_TOO_LARGE",
            details={"max_bytes": app.config.get("MAX_CONTENT_LENGTH")},
        )
        return json_response(payload, status_code=413)

    @app.errorhandler(APIError)
    def handle_api_error(e: APIError) -> Response:
        payload = error_payload(
            message=e.message,
            code=e.code,
            details=e.details,
        )
        return json_response(payload, status_code=e.status_code)

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException) -> Response:
        status_code = e.code if e.code is not None else 500
        message = e.description or "HTTP error"
        payload = error_payload(
            message=message,
            code=_http_status_to_error_code(status_code),
            details={"http_error": e.name},
        )
        return json_response(payload, status_code=status_code)

    @app.errorhandler(Exception)
    def handle_generic_exception(e: Exception) -> Response:
        request_id = str(getattr(g, "request_id", "n/a"))
        app.logger.exception("Unhandled exception. request_id=%s", request_id)
        payload = error_payload(
            message="An unexpected error occurred.",
            code="INTERNAL_ERROR",
            details={"request_id": request_id},
        )
        return json_response(payload, status_code=500)
