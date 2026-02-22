import uuid
from typing import Dict

from app.application.services.password_reset_service import (
    PASSWORD_RESET_INVALID_TOKEN_MESSAGE,
    PASSWORD_RESET_NEUTRAL_MESSAGE,
    PASSWORD_RESET_SUCCESS_MESSAGE,
)


def _register_payload(suffix: str, password: str = "StrongPass@123") -> Dict[str, str]:
    return {
        "name": f"user-{suffix}",
        "email": f"auth-contract-{suffix}@email.com",
        "password": password,
    }


def _v2_headers() -> Dict[str, str]:
    return {"X-API-Contract": "v2"}


def test_auth_register_v1_legacy_contract(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    response = client.post("/auth/register", json=_register_payload(suffix))

    assert response.status_code == 201
    body = response.get_json()
    assert "success" not in body
    assert body["message"] == "User created successfully"
    assert "data" in body
    assert "id" in body["data"]


def test_auth_register_v2_contract(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/auth/register",
        headers=_v2_headers(),
        json=_register_payload(suffix),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "User created successfully"
    assert "user" in body["data"]


def test_auth_register_validation_error_v2_contract(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/auth/register",
        headers=_v2_headers(),
        json=_register_payload(suffix, password="123"),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_auth_login_v1_legacy_contract(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    response = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "success" not in body
    assert "token" in body
    assert "user" in body


def test_auth_login_v2_contract(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    response = client.post(
        "/auth/login",
        headers=_v2_headers(),
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "token" in body["data"]
    assert "user" in body["data"]


def test_auth_login_invalid_credentials_v2_contract(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    response = client.post(
        "/auth/login",
        headers=_v2_headers(),
        json={"email": payload["email"], "password": "WrongPass@123"},
    )

    assert response.status_code == 401
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_auth_logout_v2_contract(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    login = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    token = login.get_json()["token"]

    response = client.post(
        "/auth/logout",
        headers={
            "Authorization": f"Bearer {token}",
            "X-API-Contract": "v2",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Logout successful"
    assert body["data"] == {}


def test_auth_password_forgot_v2_contract_is_neutral_for_unknown_email(client) -> None:
    response = client.post(
        "/auth/password/forgot",
        headers=_v2_headers(),
        json={"email": "unknown-user@email.com"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == PASSWORD_RESET_NEUTRAL_MESSAGE
    assert body["data"] == {}


def test_auth_password_forgot_v2_contract_dispatches_token_for_known_user(
    client,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    response = client.post(
        "/auth/password/forgot",
        headers=_v2_headers(),
        json={"email": payload["email"]},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == PASSWORD_RESET_NEUTRAL_MESSAGE
    outbox = client.application.extensions.get("password_reset_outbox", [])
    assert isinstance(outbox, list)
    assert len(outbox) == 1
    assert outbox[0]["email"] == payload["email"]
    assert isinstance(outbox[0]["token"], str) and outbox[0]["token"]


def test_auth_password_reset_v2_contract_with_invalid_token(client) -> None:
    response = client.post(
        "/auth/password/reset",
        headers=_v2_headers(),
        json={
            "token": "invalid-token-value-with-sufficient-length-123456",
            "new_password": "NovaSenha@123",
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["message"] == PASSWORD_RESET_INVALID_TOKEN_MESSAGE


def test_auth_password_reset_v2_contract_revokes_existing_sessions(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    login = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    old_token = login.get_json()["token"]

    forgot = client.post(
        "/auth/password/forgot",
        headers=_v2_headers(),
        json={"email": payload["email"]},
    )
    assert forgot.status_code == 200
    outbox = client.application.extensions.get("password_reset_outbox", [])
    assert isinstance(outbox, list)
    token = outbox[0]["token"]

    reset = client.post(
        "/auth/password/reset",
        headers=_v2_headers(),
        json={"token": token, "new_password": "NovaSenha@123"},
    )
    assert reset.status_code == 200
    reset_body = reset.get_json()
    assert reset_body["success"] is True
    assert reset_body["message"] == PASSWORD_RESET_SUCCESS_MESSAGE

    me_with_old_token = client.get(
        "/user/me?page=1&limit=10",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert me_with_old_token.status_code == 401

    old_login = client.post(
        "/auth/login",
        headers=_v2_headers(),
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        headers=_v2_headers(),
        json={"email": payload["email"], "password": "NovaSenha@123"},
    )
    assert new_login.status_code == 200
