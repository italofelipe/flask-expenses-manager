from typing import Any, Dict
from uuid import UUID

from flask import jsonify
from flask_jwt_extended import JWTManager, get_jwt_identity

from app.extensions.database import db
from app.models.user import User
from app.utils.api_contract import is_v2_contract_request
from app.utils.response_builder import error_payload


def _jwt_error_response(message: str, *, code: str, status_code: int) -> Any:
    if is_v2_contract_request():
        return (
            jsonify(error_payload(message=message, code=code, details={})),
            status_code,
        )
    return jsonify({"message": message}), status_code


def is_token_revoked(jti: str) -> bool:
    # Keep compatibility with legacy call sites that still invoke this helper.
    # Runtime revocation source-of-truth is persisted in user.current_jti.
    try:
        identity = get_jwt_identity()
        if not identity:
            return True
        user = db.session.get(User, UUID(str(identity)))
        return not user or user.current_jti != jti
    except Exception:
        return True


def register_jwt_callbacks(jwt: JWTManager) -> None:
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> bool:
        user_id = jwt_payload.get("sub")
        jti = jwt_payload.get("jti")

        if not user_id or not jti:
            return True

        user = db.session.get(User, UUID(user_id))
        return not user or user.current_jti != jti

    @jwt.revoked_token_loader
    def revoked_token_callback(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> Any:
        return _jwt_error_response(
            "Token revogado",
            code="UNAUTHORIZED",
            status_code=401,
        )

    @jwt.invalid_token_loader
    def invalid_token_callback(error: str) -> Any:
        return _jwt_error_response(
            "Token inválido",
            code="UNAUTHORIZED",
            status_code=401,
        )

    @jwt.expired_token_loader
    def expired_token_callback(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> Any:
        return _jwt_error_response(
            "Token expirado",
            code="UNAUTHORIZED",
            status_code=401,
        )

    @jwt.unauthorized_loader
    def missing_token_callback(error: str) -> Any:
        return _jwt_error_response(
            "Token ausente",
            code="UNAUTHORIZED",
            status_code=401,
        )
