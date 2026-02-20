from typing import Any

from flask import current_app, request
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException

from app.extensions.jwt_callbacks import _jwt_error_response


def register_auth_guard(app: Any) -> None:
    @app.before_request  # type: ignore[misc]
    def auth_guard() -> Any:
        # Liveness endpoint must remain public for infra health checks.
        if request.path.rstrip("/") == "/healthz":
            return
        open_endpoints = {
            "registerresource",
            "authresource",
            "refreshtokenresource",
            "execute_graphql",
            "static",
            "swaggerui.index",
            "swaggerui.static",
            "swaggerui.swagger_json",
            "swagger-ui",
            "swagger-ui.static",
            "swagger-ui.swagger_json",
        }
        if not request.endpoint:
            return
        if request.path.startswith("/docs"):
            return
        endpoint = request.endpoint.split(".")[-1]
        if endpoint in open_endpoints:
            return

        try:
            verify_jwt_in_request()
        except JWTExtendedException:
            return _jwt_error_response(
                "Token inválido ou ausente",
                code="UNAUTHORIZED",
                status_code=401,
            )
        except Exception:
            current_app.logger.exception(
                "Unexpected failure while validating JWT in auth guard."
            )
            return _jwt_error_response(
                "Internal Server Error",
                code="INTERNAL_ERROR",
                status_code=500,
            )
