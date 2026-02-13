from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationConflictPolicyDTO:
    conceal_conflict: bool
    accepted_message: str
    created_message: str
    conflict_message: str


@dataclass(frozen=True)
class LoginGuardPolicyDTO:
    expose_known_principal: bool


@dataclass(frozen=True)
class AuthSecurityPolicyDTO:
    registration: RegistrationConflictPolicyDTO
    login_guard: LoginGuardPolicyDTO
