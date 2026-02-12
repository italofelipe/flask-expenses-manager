from __future__ import annotations

import uuid
from typing import Any

from app.services.login_attempt_guard_service import (
    get_login_attempt_guard,
    reset_login_attempt_guard_for_tests,
)


def _register_payload(suffix: str) -> dict[str, str]:
    return {
        "name": f"guard-backend-{suffix}",
        "email": f"guard-backend-{suffix}@email.com",
        "password": "StrongPass@123",
    }


def _graphql(
    client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
) -> Any:
    return client.post("/graphql", json={"query": query, "variables": variables or {}})


def test_login_guard_uses_memory_backend_by_default(monkeypatch: Any) -> None:
    monkeypatch.delenv("LOGIN_GUARD_BACKEND", raising=False)
    monkeypatch.delenv("LOGIN_GUARD_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    reset_login_attempt_guard_for_tests()

    guard = get_login_attempt_guard()

    assert guard.backend_name == "memory"
    assert guard.configured_backend == "memory"
    assert guard.backend_ready is True


def test_login_guard_falls_back_to_memory_when_redis_url_missing(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_BACKEND", "redis")
    monkeypatch.delenv("LOGIN_GUARD_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("LOGIN_GUARD_FAIL_CLOSED", "false")
    reset_login_attempt_guard_for_tests()

    guard = get_login_attempt_guard()

    assert guard.backend_name == "memory"
    assert guard.configured_backend == "redis"
    assert guard.backend_ready is False
    assert guard.fail_closed is False


def test_login_rest_returns_503_when_login_guard_fail_closed(
    client: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_BACKEND", "redis")
    monkeypatch.delenv("LOGIN_GUARD_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("LOGIN_GUARD_FAIL_CLOSED", "true")
    reset_login_attempt_guard_for_tests()

    payload = _register_payload(uuid.uuid4().hex[:8])
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    response = client.post(
        "/auth/login",
        headers={"X-API-Contract": "v2"},
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code == 503
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_BACKEND_UNAVAILABLE"


def test_login_rest_uses_memory_fallback_when_fail_closed_disabled(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_BACKEND", "redis")
    monkeypatch.delenv("LOGIN_GUARD_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("LOGIN_GUARD_FAIL_CLOSED", "false")
    reset_login_attempt_guard_for_tests()

    payload = _register_payload(uuid.uuid4().hex[:8])
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    response = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code == 200


def test_login_graphql_returns_backend_unavailable_when_fail_closed(
    client: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LOGIN_GUARD_ENABLED", "true")
    monkeypatch.setenv("LOGIN_GUARD_BACKEND", "redis")
    monkeypatch.delenv("LOGIN_GUARD_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("LOGIN_GUARD_FAIL_CLOSED", "true")
    reset_login_attempt_guard_for_tests()

    payload = _register_payload(uuid.uuid4().hex[:8])
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    response = _graphql(
        client,
        mutation,
        {"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code in {200, 400}
    body = response.get_json()
    assert "errors" in body
    error = body["errors"][0]
    assert (
        error["message"] == "Authentication temporarily unavailable. Try again later."
    )
    assert error["extensions"]["code"] == "AUTH_BACKEND_UNAVAILABLE"
