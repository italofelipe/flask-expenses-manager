"""Session management endpoints — list, revoke, and global logout.

GET  /auth/sessions          — list active sessions
DELETE /auth/sessions/{id}   — revoke a specific session
DELETE /auth/sessions        — revoke all sessions (global logout)
"""

from __future__ import annotations

from uuid import UUID

from flask import Response
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt

from app.application.services.session_service import (
    SessionNotFoundError,
    list_sessions,
    revoke_all_sessions,
    revoke_session,
)
from app.auth import current_user_id
from app.controllers.transaction.utils import _guard_revoked_token
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_error, compat_success


class SessionListResource(MethodResource):
    """GET /auth/sessions — list all active sessions for the current user."""

    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid: UUID = current_user_id()
        claims = get_jwt()
        current_jti: str | None = claims.get("jti")

        sessions = list_sessions(user_id=user_uuid, current_access_jti=current_jti)
        return compat_success(
            legacy_payload={"sessions": sessions},
            status_code=200,
            message="Sessions listed successfully",
            data={"sessions": sessions},
        )


class SessionRevokeAllResource(MethodResource):
    """DELETE /auth/sessions — revoke all sessions (global logout)."""

    @jwt_required()
    def delete(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid: UUID = current_user_id()
        count = revoke_all_sessions(user_id=user_uuid)
        return compat_success(
            legacy_payload={"revoked": count},
            status_code=200,
            message=f"{count} session(s) revoked",
            data={"revoked": count},
        )


class SessionRevokeResource(MethodResource):
    """DELETE /auth/sessions/<session_id> — revoke a specific session."""

    @jwt_required()
    def delete(self, session_id: str) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid: UUID = current_user_id()
        try:
            revoke_session(session_id=UUID(session_id), user_id=user_uuid)
        except (ValueError, SessionNotFoundError):
            return compat_error(
                legacy_payload={"error": "Session not found"},
                status_code=404,
                message="Session not found",
                error_code="SESSION_NOT_FOUND",
            )
        return compat_success(
            legacy_payload={"revoked": session_id},
            status_code=200,
            message="Session revoked",
            data={"revoked": session_id},
        )


__all__ = ["SessionListResource", "SessionRevokeAllResource", "SessionRevokeResource"]
