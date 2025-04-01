from typing import Any, Dict
from uuid import UUID

from flask import jsonify
from flask_jwt_extended import JWTManager

from app.models.user import User

# Simples set para armazenar tokens revogados em memória
revoked_tokens: set[str] = set()


def is_token_revoked(jti: str) -> bool:
    return jti in revoked_tokens


def register_jwt_callbacks(jwt: JWTManager) -> None:
    @jwt.token_in_blocklist_loader  # type: ignore[misc]
    def check_if_token_revoked(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> bool:
        user_id = jwt_payload.get("sub")
        jti = jwt_payload.get("jti")

        if not user_id or not jti:
            return True

        user = User.query.get(UUID(user_id))
        return not user or user.current_jti != jti

    @jwt.revoked_token_loader  # type: ignore[misc]
    def revoked_token_callback(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> Any:
        return jsonify({"message": "Token revogado"}), 401

    @jwt.invalid_token_loader  # type: ignore[misc]
    def invalid_token_callback(error: str) -> Any:
        return jsonify({"message": "Token inválido"}), 422

    @jwt.expired_token_loader  # type: ignore[misc]
    def expired_token_callback(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> Any:
        return jsonify({"message": "Token expirado"}), 401

    @jwt.unauthorized_loader  # type: ignore[misc]
    def missing_token_callback(error: str) -> Any:
        return jsonify({"message": "Token ausente"}), 401
