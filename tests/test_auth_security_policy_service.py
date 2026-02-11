from __future__ import annotations

from typing import Any

import pytest

from app.application.services.auth_security_policy_service import (
    get_auth_security_policy,
    reset_auth_security_policy_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_policy_cache() -> None:
    reset_auth_security_policy_for_tests()
    yield
    reset_auth_security_policy_for_tests()


def test_auth_security_policy_defaults_to_legacy_compatibility() -> None:
    policy = get_auth_security_policy()

    assert policy.registration.conceal_conflict is False
    assert policy.registration.accepted_message == "Registration request accepted."
    assert policy.registration.created_message == "User created successfully"
    assert policy.registration.conflict_message == "Email already registered"
    assert policy.login_guard.expose_known_principal is True


def test_auth_security_policy_reads_env_overrides(monkeypatch: Any) -> None:
    monkeypatch.setenv("AUTH_CONCEAL_REGISTRATION_CONFLICT", "true")
    monkeypatch.setenv("AUTH_REGISTRATION_ACCEPTED_MESSAGE", "Accepted")
    monkeypatch.setenv("AUTH_REGISTRATION_CREATED_MESSAGE", "Created")
    monkeypatch.setenv("AUTH_REGISTRATION_CONFLICT_MESSAGE", "Conflict")
    monkeypatch.setenv("AUTH_LOGIN_GUARD_EXPOSE_KNOWN_PRINCIPAL", "false")
    reset_auth_security_policy_for_tests()

    policy = get_auth_security_policy()

    assert policy.registration.conceal_conflict is True
    assert policy.registration.accepted_message == "Accepted"
    assert policy.registration.created_message == "Created"
    assert policy.registration.conflict_message == "Conflict"
    assert policy.login_guard.expose_known_principal is False
