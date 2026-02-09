import uuid
from typing import Dict


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
