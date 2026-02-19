from typing import Any, cast
from uuid import UUID

from flask import request
from flask_jwt_extended import decode_token

from app.extensions.database import db
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_UNAUTHORIZED,
    build_public_graphql_error,
)
from app.models.user import User


def _extract_bearer_token() -> str | None:
    auth_header = str(request.headers.get("Authorization", "")).strip()
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    return token or None


def get_current_user_optional() -> User | None:
    token = _extract_bearer_token()
    if not token:
        return None
    try:
        jwt_payload: dict[str, Any] = decode_token(token)
    except Exception:
        return None

    user_id = jwt_payload.get("sub")
    jti = jwt_payload.get("jti")
    if not user_id or not jti:
        return None

    user = cast(User | None, db.session.get(User, UUID(str(user_id))))
    if not user or user.current_jti != str(jti):
        return None
    return user


def get_current_user_required() -> User:
    user = get_current_user_optional()
    if user is None:
        raise build_public_graphql_error(
            "Token inválido ou ausente.",
            code=GRAPHQL_ERROR_CODE_UNAUTHORIZED,
        )
    return user
