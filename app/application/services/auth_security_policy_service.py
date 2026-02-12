from __future__ import annotations

import os

from app.application.dto.auth_security_policy_dto import (
    AuthSecurityPolicyDTO,
    LoginGuardPolicyDTO,
    RegistrationConflictPolicyDTO,
)


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_text_env(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _is_relaxed_auth_security_runtime() -> bool:
    return _read_bool_env("FLASK_DEBUG", False) or _read_bool_env(
        "FLASK_TESTING", False
    )


def _build_policy() -> AuthSecurityPolicyDTO:
    relaxed_runtime = _is_relaxed_auth_security_runtime()
    conceal_registration_conflict = _read_bool_env(
        "AUTH_CONCEAL_REGISTRATION_CONFLICT",
        not relaxed_runtime,
    )
    expose_known_principal = _read_bool_env(
        "AUTH_LOGIN_GUARD_EXPOSE_KNOWN_PRINCIPAL",
        relaxed_runtime,
    )
    accepted_message = _read_text_env(
        "AUTH_REGISTRATION_ACCEPTED_MESSAGE",
        "Registration request accepted.",
    )
    created_message = _read_text_env(
        "AUTH_REGISTRATION_CREATED_MESSAGE",
        "User created successfully",
    )
    conflict_message = _read_text_env(
        "AUTH_REGISTRATION_CONFLICT_MESSAGE",
        "Email already registered",
    )
    return AuthSecurityPolicyDTO(
        registration=RegistrationConflictPolicyDTO(
            conceal_conflict=conceal_registration_conflict,
            accepted_message=accepted_message,
            created_message=created_message,
            conflict_message=conflict_message,
        ),
        login_guard=LoginGuardPolicyDTO(
            expose_known_principal=expose_known_principal,
        ),
    )


_auth_security_policy: AuthSecurityPolicyDTO | None = None


def get_auth_security_policy() -> AuthSecurityPolicyDTO:
    global _auth_security_policy
    if _auth_security_policy is None:
        _auth_security_policy = _build_policy()
    return _auth_security_policy


def reset_auth_security_policy_for_tests() -> None:
    global _auth_security_policy
    _auth_security_policy = None
