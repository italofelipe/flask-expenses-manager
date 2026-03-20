from flask import Flask, current_app, request
from flask.typing import ResponseReturnValue
from flask_jwt_extended.exceptions import JWTExtendedException

from app.auth import AuthContextError, get_active_auth_context
from app.extensions.jwt_callbacks import _jwt_error_response


def register_auth_guard(app: Flask) -> None:
    def auth_guard() -> ResponseReturnValue | None:
        if request.method == "OPTIONS":
            return None
        # Liveness endpoint must remain public for infra health checks.
        if request.path.rstrip("/") == "/healthz":
            return None
        open_endpoints = {
            "registerresource",
            "authresource",
            "forgotpasswordresource",
            "resetpasswordresource",
            "refreshtokenresource",
            "execute_graphql",
            "static",
            "swaggerui.index",
            "swaggerui.static",
            "swaggerui.swagger_json",
            "swagger-ui",
            "swagger-ui.static",
            "swagger-ui.swagger_json",
            "installment_vs_cash_calculation",
            # Billing webhook — provider calls this directly without JWT
            "handle_webhook",
        }
        if not request.endpoint:
            return None
        if request.path.startswith("/docs"):
            return None
        endpoint = request.endpoint.split(".")[-1]
        if endpoint in open_endpoints:
            return None

        try:
            get_active_auth_context()
        except (JWTExtendedException, AuthContextError):
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

        return None

    app.before_request(auth_guard)
