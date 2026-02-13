from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.application.services.auth_security_policy_service import (
    reset_auth_security_policy_for_tests,
)
from app.models.user import User
from app.services.login_attempt_guard_service import reset_login_attempt_guard_for_tests


def _register_payload(suffix: str) -> dict[str, str]:
    return {
        "name": f"user-{suffix}",
        "email": f"policy-{suffix}@email.com",
        "password": "StrongPass@123",
    }


def _graphql(
    client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
) -> Any:
    return client.post("/graphql", json={"query": query, "variables": variables or {}})


@pytest.fixture(autouse=True)
def _reset_policy_state() -> None:
    reset_auth_security_policy_for_tests()
    reset_login_attempt_guard_for_tests()
    yield
    reset_auth_security_policy_for_tests()
    reset_login_attempt_guard_for_tests()


def test_rest_register_can_conceal_duplicate_conflict(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("AUTH_CONCEAL_REGISTRATION_CONFLICT", "true")
    reset_auth_security_policy_for_tests()

    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)

    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = first.get_json()
    second_body = second.get_json()
    assert first_body["message"] == "Registration request accepted."
    assert second_body["message"] == "Registration request accepted."
    assert first_body["data"] == {}
    assert second_body["data"] == {}

    with client.application.app_context():
        assert User.query.filter_by(email=payload["email"]).count() == 1


def test_graphql_register_can_conceal_duplicate_conflict(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("AUTH_CONCEAL_REGISTRATION_CONFLICT", "true")
    reset_auth_security_policy_for_tests()

    suffix = uuid.uuid4().hex[:8]
    mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) {
        message
        user { id }
      }
    }
    """
    variables = {
        "name": f"user-{suffix}",
        "email": f"policy-graphql-{suffix}@email.com",
        "password": "StrongPass@123",
    }

    first = _graphql(client, mutation, variables)
    second = _graphql(client, mutation, variables)

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.get_json()
    second_body = second.get_json()
    assert "errors" not in first_body
    assert "errors" not in second_body
    assert (
        first_body["data"]["registerUser"]["message"]
        == "Registration request accepted."
    )
    assert (
        second_body["data"]["registerUser"]["message"]
        == "Registration request accepted."
    )
    assert first_body["data"]["registerUser"]["user"] is None
    assert second_body["data"]["registerUser"]["user"] is None


def test_rest_login_guard_can_hide_known_principal_signal(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_FAILURE_THRESHOLD", "3")
    monkeypatch.setenv("LOGIN_GUARD_KNOWN_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("LOGIN_GUARD_BASE_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("LOGIN_GUARD_MAX_COOLDOWN_SECONDS", "120")
    monkeypatch.setenv("LOGIN_GUARD_KNOWN_BASE_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("LOGIN_GUARD_KNOWN_MAX_COOLDOWN_SECONDS", "120")
    monkeypatch.setenv("AUTH_LOGIN_GUARD_EXPOSE_KNOWN_PRINCIPAL", "false")
    reset_login_attempt_guard_for_tests()
    reset_auth_security_policy_for_tests()

    payload = _register_payload(uuid.uuid4().hex[:8])
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    wrong = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": "WrongPass@123"},
    )
    assert wrong.status_code == 401

    valid = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert valid.status_code == 200
