from flask import Flask, Response, jsonify
from werkzeug.exceptions import HTTPException

JSON_MIMETYPE = "application/json"


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)  # type: ignore[misc]
    def handle_http_exception(e: HTTPException) -> Response:
        return Response(
            jsonify(
                {
                    "error": e.name,
                    "message": e.description,
                }
            ).get_data(as_text=True),
            status=e.code,
            mimetype=JSON_MIMETYPE,
        )

    @app.errorhandler(Exception)  # type: ignore[misc]
    def handle_generic_exception(e: Exception) -> Response:
        app.logger.error(f"Unhandled Exception: {str(e)}")
        return Response(
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                }
            ).get_data(as_text=True),
            status=500,
            mimetype=JSON_MIMETYPE,
        )
