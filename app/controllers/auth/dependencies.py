from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, cast
from uuid import UUID

from flask import Flask, current_app
from flask_jwt_extended import create_access_token, get_jti
from werkzeug.security import generate_password_hash

from app.application.dto.auth_security_policy_dto import AuthSecurityPolicyDTO
from app.application.services.auth_security_policy_service import (
    get_auth_security_policy,
)
from app.application.services.password_verification_service import (
    verify_password_with_timing_protection,
)
from app.models.user import User
from app.services.login_attempt_guard_service import (
    LoginAttemptContext,
    LoginAttemptGuardService,
    build_login_attempt_context,
    get_login_attempt_guard,
)

AUTH_DEPENDENCIES_EXTENSION_KEY = "auth_dependencies"


@dataclass(frozen=True)
class AuthDependencies:
    get_auth_security_policy: Callable[[], AuthSecurityPolicyDTO]
    get_login_attempt_guard: Callable[[], LoginAttemptGuardService]
    build_login_attempt_context: Callable[..., LoginAttemptContext]
    verify_password: Callable[[str | None, str], bool]
    hash_password: Callable[[str], str]
    create_access_token: Callable[[str], str]
    get_token_jti: Callable[[str], str]
    find_user_by_email: Callable[[str], User | None]
    find_user_by_name: Callable[[str], User | None]
    get_user_by_id: Callable[[UUID], User | None]


def _find_user_by_email(email: str) -> User | None:
    return cast(User | None, User.query.filter_by(email=email).first())


def _find_user_by_name(name: str) -> User | None:
    return cast(User | None, User.query.filter_by(name=name).first())


def _get_user_by_id(user_id: UUID) -> User | None:
    return cast(User | None, User.query.filter_by(id=user_id).first())


def _create_access_token_with_default_expiry(identity: str) -> str:
    return cast(
        str,
        create_access_token(identity=identity, expires_delta=timedelta(hours=1)),
    )


def _verify_password(password_hash: str | None, plain_password: str) -> bool:
    return verify_password_with_timing_protection(
        password_hash=password_hash,
        plain_password=plain_password,
    )


def _get_token_jti(token: str) -> str:
    jti = get_jti(token)
    if not jti:
        raise RuntimeError("Token JTI is missing.")
    return str(jti)


def _default_dependencies() -> AuthDependencies:
    return AuthDependencies(
        get_auth_security_policy=get_auth_security_policy,
        get_login_attempt_guard=get_login_attempt_guard,
        build_login_attempt_context=build_login_attempt_context,
        verify_password=_verify_password,
        hash_password=generate_password_hash,
        create_access_token=_create_access_token_with_default_expiry,
        get_token_jti=_get_token_jti,
        find_user_by_email=_find_user_by_email,
        find_user_by_name=_find_user_by_name,
        get_user_by_id=_get_user_by_id,
    )


def register_auth_dependencies(
    app: Flask,
    dependencies: AuthDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(AUTH_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_auth_dependencies() -> AuthDependencies:
    configured = current_app.extensions.get(AUTH_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, AuthDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[AUTH_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
