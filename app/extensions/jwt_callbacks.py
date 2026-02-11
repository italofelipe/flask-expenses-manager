from typing import Any, Dict
from uuid import UUID

from flask import has_request_context, jsonify, request
from flask_jwt_extended import JWTManager

from app.models.user import User
from app.utils.response_builder import error_payload

CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"


def _is_v2_contract() -> bool:
    if not has_request_context():
        return False
    return str(request.headers.get(CONTRACT_HEADER, "")).strip().lower() == CONTRACT_V2


def _jwt_error_response(message: str, *, code: str, status_code: int) -> Any:
    if _is_v2_contract():
        return (
            jsonify(error_payload(message=message, code=code, details={})),
            status_code,
        )
    return jsonify({"message": message}), status_code


def is_token_revoked(jti: str) -> bool:
    # Revocation is enforced by token_in_blocklist_loader against
    # persisted user.current_jti.
    # This helper remains for backward-compatible call sites.
    return False


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
        return _jwt_error_response(
            "Token revogado",
            code="UNAUTHORIZED",
            status_code=401,
        )

    @jwt.invalid_token_loader  # type: ignore[misc]
    def invalid_token_callback(error: str) -> Any:
        return _jwt_error_response(
            "Token inválido",
            code="UNAUTHORIZED",
            status_code=401,
        )

    @jwt.expired_token_loader  # type: ignore[misc]
    def expired_token_callback(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> Any:
        return _jwt_error_response(
            "Token expirado",
            code="UNAUTHORIZED",
            status_code=401,
        )

    @jwt.unauthorized_loader  # type: ignore[misc]
    def missing_token_callback(error: str) -> Any:
        return _jwt_error_response(
            "Token ausente",
            code="UNAUTHORIZED",
            status_code=401,
        )
