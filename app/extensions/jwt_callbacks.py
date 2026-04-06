from typing import Any, Dict
from uuid import UUID

from flask import jsonify
from flask.typing import ResponseReturnValue
from flask_jwt_extended import JWTManager

from app.auth import InvalidAuthContextError, current_user_id
from app.extensions.database import db
from app.extensions.jwt_revocation_cache import get_jwt_revocation_cache
from app.models.user import User
from app.utils.api_contract import is_v2_contract_request
from app.utils.response_builder import error_payload


def _jwt_error_response(
    message: str, *, code: str, status_code: int
) -> ResponseReturnValue:
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
        identity = current_user_id(optional=True)
        if identity is None:
            return True
        user = db.session.get(User, identity)
        return not user or user.current_jti != jti
    except InvalidAuthContextError:
        return True


def _is_access_token_revoked(user_id: str, jti: str) -> bool:
    """Check access token revocation using Redis cache (DB fallback on miss)."""
    cache = get_jwt_revocation_cache()
    cached_jti = cache.get_current_jti(user_id)
    if cached_jti is not None:
        return cached_jti != jti
    user = db.session.get(User, UUID(user_id))
    if not user:
        return True
    cache.set_current_jti(user_id, user.current_jti)
    return bool(user.current_jti != jti)


def _is_refresh_token_revoked(user_id: str, jti: str) -> bool:
    """Check refresh token revocation directly against the DB (not cached)."""
    user = db.session.get(User, UUID(user_id))
    if not user:
        return True
    return bool(user.refresh_token_jti != jti)


def register_jwt_callbacks(jwt: JWTManager) -> None:
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(
        jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]
    ) -> bool:
        user_id = jwt_payload.get("sub")
        jti = jwt_payload.get("jti")
        token_type = jwt_payload.get("type", "access")

        if not user_id or not jti:
            return True

        if token_type == "refresh":
            return _is_refresh_token_revoked(user_id, jti)
        return _is_access_token_revoked(user_id, jti)

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
