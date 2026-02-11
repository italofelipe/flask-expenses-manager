from __future__ import annotations

from typing import Any

from app.extensions.integration_metrics import reset_metrics_for_tests, snapshot_metrics
from app.services.login_attempt_guard_service import reset_login_attempt_guard_for_tests


def _register_payload(email: str, name: str = "guard-user") -> dict[str, str]:
    return {
        "name": name,
        "email": email,
        "password": "StrongPass@123",
    }


def _graphql(
    client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
):
    return client.post("/graphql", json={"query": query, "variables": variables or {}})


def test_rest_login_guard_blocks_after_threshold(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("LOGIN_GUARD_BASE_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("LOGIN_GUARD_MAX_COOLDOWN_SECONDS", "120")
    reset_login_attempt_guard_for_tests()

    email = "login-guard-rest@email.com"
    register = client.post("/auth/register", json=_register_payload(email=email))
    assert register.status_code == 201

    first = client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    second = client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    blocked = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass@123"},
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert blocked.status_code == 429
    blocked_body = blocked.get_json()
    assert blocked_body["message"] == "Too many login attempts. Try again later."
    assert int(blocked_body["retry_after_seconds"]) >= 1


def test_graphql_login_guard_blocks_after_threshold(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("LOGIN_GUARD_BASE_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("LOGIN_GUARD_MAX_COOLDOWN_SECONDS", "120")
    reset_login_attempt_guard_for_tests()

    email = "login-guard-graphql@email.com"
    register = client.post("/auth/register", json=_register_payload(email=email))
    assert register.status_code == 201

    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    first = _graphql(
        client,
        login_mutation,
        {"email": email, "password": "wrong-password"},
    )
    second = _graphql(
        client,
        login_mutation,
        {"email": email, "password": "wrong-password"},
    )
    blocked = _graphql(
        client,
        login_mutation,
        {"email": email, "password": "StrongPass@123"},
    )

    assert first.status_code in {200, 400}
    assert second.status_code in {200, 400}
    blocked_body = blocked.get_json()
    assert blocked.status_code in {200, 400}
    assert blocked_body is not None
    assert "errors" in blocked_body
    assert (
        blocked_body["errors"][0]["message"]
        == "Too many login attempts. Try again later."
    )


def test_rest_login_guard_uses_known_principal_policy(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_FAILURE_THRESHOLD", "10")
    monkeypatch.setenv("LOGIN_GUARD_KNOWN_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("LOGIN_GUARD_BASE_COOLDOWN_SECONDS", "30")
    monkeypatch.setenv("LOGIN_GUARD_KNOWN_BASE_COOLDOWN_SECONDS", "90")
    monkeypatch.setenv("LOGIN_GUARD_MAX_COOLDOWN_SECONDS", "120")
    monkeypatch.setenv("LOGIN_GUARD_KNOWN_MAX_COOLDOWN_SECONDS", "180")
    reset_login_attempt_guard_for_tests()

    email = "login-known-policy@email.com"
    register = client.post("/auth/register", json=_register_payload(email=email))
    assert register.status_code == 201

    first = client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    second = client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    blocked = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass@123"},
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert blocked.status_code == 429


def test_login_guard_emits_operational_metrics(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("LOGIN_GUARD_BASE_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("LOGIN_GUARD_MAX_COOLDOWN_SECONDS", "120")
    reset_login_attempt_guard_for_tests()
    reset_metrics_for_tests()

    email = "login-metrics@email.com"
    register = client.post("/auth/register", json=_register_payload(email=email))
    assert register.status_code == 201

    client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    blocked = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass@123"},
    )
    assert blocked.status_code == 429

    metrics = snapshot_metrics(prefix="login_guard.")
    assert metrics["login_guard.failure"] >= 2
    assert metrics["login_guard.check.blocked"] >= 1
    assert metrics["login_guard.cooldown.started"] >= 1
