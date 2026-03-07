from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast, overload
from uuid import UUID

from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError

from app.extensions.database import db
from app.models.user import User


class AuthContextError(RuntimeError):
    """Base error for framework-agnostic auth context resolution."""


class InvalidAuthContextError(AuthContextError):
    """Raised when the request carries invalid or incomplete auth claims."""


class RevokedTokenError(AuthContextError):
    """Raised when the token is structurally valid but no longer active."""


@dataclass(frozen=True)
class AuthContext:
    subject: str
    email: str | None
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    jti: str | None
    issued_at: datetime | None
    expires_at: datetime | None
    raw_claims: Mapping[str, object]


def _claim_as_str(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _claim_as_sequence(payload: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _claim_as_datetime(payload: Mapping[str, object], key: str) -> datetime | None:
    value = payload.get(key)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def auth_context_from_claims(payload: Mapping[str, object]) -> AuthContext:
    subject = _claim_as_str(payload, "sub")
    if subject is None:
        raise InvalidAuthContextError("JWT is missing subject claim.")
    return AuthContext(
        subject=subject,
        email=_claim_as_str(payload, "email"),
        roles=_claim_as_sequence(payload, "roles"),
        permissions=_claim_as_sequence(payload, "permissions"),
        jti=_claim_as_str(payload, "jti"),
        issued_at=_claim_as_datetime(payload, "iat"),
        expires_at=_claim_as_datetime(payload, "exp"),
        raw_claims=payload,
    )


@overload
def get_current_auth_context(*, optional: Literal[False] = False) -> AuthContext: ...


@overload
def get_current_auth_context(*, optional: Literal[True]) -> AuthContext | None: ...


def get_current_auth_context(*, optional: bool = False) -> AuthContext | None:
    return _get_current_auth_context(optional=optional)


def _get_current_auth_context(*, optional: bool) -> AuthContext | None:
    try:
        verify_jwt_in_request(optional=optional)
    except NoAuthorizationError:
        if optional:
            return None
        raise
    payload = cast(Mapping[str, object], get_jwt())
    if not payload:
        if optional:
            return None
        raise InvalidAuthContextError("JWT payload is empty.")
    return auth_context_from_claims(payload)


@overload
def current_user_id(*, optional: Literal[False] = False) -> UUID: ...


@overload
def current_user_id(*, optional: Literal[True]) -> UUID | None: ...


def current_user_id(*, optional: bool = False) -> UUID | None:
    context = _get_current_auth_context(optional=optional)
    if context is None:
        return None
    try:
        return UUID(context.subject)
    except ValueError as exc:
        raise InvalidAuthContextError("JWT subject is not a valid UUID.") from exc


@overload
def current_token_jti(*, optional: Literal[False] = False) -> str | None: ...


@overload
def current_token_jti(*, optional: Literal[True]) -> str | None: ...


def current_token_jti(*, optional: bool = False) -> str | None:
    context = _get_current_auth_context(optional=optional)
    if context is None:
        return None
    return str(context.jti) if context.jti is not None else None


def _user_from_auth_context(context: AuthContext) -> User | None:
    try:
        user_id = UUID(context.subject)
    except ValueError as exc:
        raise InvalidAuthContextError("JWT subject is not a valid UUID.") from exc
    return cast(User | None, db.session.get(User, user_id))


def is_auth_context_revoked(context: AuthContext) -> bool:
    user = _user_from_auth_context(context)
    return (
        user is None
        or context.jti is None
        or not hasattr(user, "current_jti")
        or user.current_jti != context.jti
    )


@overload
def get_active_auth_context(*, optional: Literal[False] = False) -> AuthContext: ...


@overload
def get_active_auth_context(*, optional: Literal[True]) -> AuthContext | None: ...


def get_active_auth_context(*, optional: bool = False) -> AuthContext | None:
    return _get_active_auth_context(optional=optional)


def _get_active_auth_context(*, optional: bool) -> AuthContext | None:
    context = _get_current_auth_context(optional=optional)
    if context is None:
        return None
    if is_auth_context_revoked(context):
        raise RevokedTokenError("JWT is revoked.")
    return context


@overload
def get_active_user(
    *, optional: Literal[False] = False
) -> tuple[AuthContext, User]: ...


@overload
def get_active_user(*, optional: Literal[True]) -> tuple[AuthContext, User] | None: ...


def get_active_user(*, optional: bool = False) -> tuple[AuthContext, User] | None:
    context = _get_active_auth_context(optional=optional)
    if context is None:
        return None
    user = _user_from_auth_context(context)
    if user is None:
        raise RevokedTokenError("JWT does not resolve to an active user.")
    return context, user
