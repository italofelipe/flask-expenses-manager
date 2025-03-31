from typing import Any

from flask import jsonify
from flask_jwt_extended import JWTManager

# Simples set para armazenar tokens revogados em memória
revoked_tokens: set[str] = set()


def register_jwt_callbacks(jwt: JWTManager) -> None:
    @jwt.token_in_blocklist_loader  # type: ignore[misc]
    def check_if_token_revoked(
        jwt_header: dict[str, Any], jwt_payload: dict[str, Any]
    ) -> bool:
        return jwt_payload["jti"] in revoked_tokens

    @jwt.revoked_token_loader  # type: ignore[misc]
    def revoked_token_callback(
        jwt_header: dict[str, Any], jwt_payload: dict[str, Any]
    ) -> Any:
        return jsonify({"message": "Token revogado"}), 401

    @jwt.invalid_token_loader  # type: ignore[misc]
    def invalid_token_callback(error: str) -> Any:
        return jsonify({"message": "Token inválido"}), 422

    @jwt.expired_token_loader  # type: ignore[misc]
    def expired_token_callback(
        jwt_header: dict[str, Any], jwt_payload: dict[str, Any]
    ) -> Any:
        return jsonify({"message": "Token expirado"}), 401

    @jwt.unauthorized_loader  # type: ignore[misc]
    def missing_token_callback(error: str) -> Any:
        return jsonify({"message": "Token ausente"}), 401
