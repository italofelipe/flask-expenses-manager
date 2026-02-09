from typing import Any

from flask import jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.extensions.jwt_callbacks import revoked_tokens


def register_auth_guard(app: Any) -> None:
    @app.before_request  # type: ignore[misc]
    def auth_guard() -> Any:
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
        print("ENDPOINT REQUISITADO:", request.endpoint)
        endpoint = request.endpoint.split(".")[-1]
        if endpoint in open_endpoints:
            return

        try:
            verify_jwt_in_request()
            jti = get_jwt()["jti"]
            if jti in revoked_tokens:
                return jsonify({"message": "Token revogado"}), 401
        except Exception:
            return jsonify({"message": "Token inválido ou ausente"}), 401
