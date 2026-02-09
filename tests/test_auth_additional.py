import uuid


def _register_payload(suffix: str, password: str = "StrongPass@123") -> dict[str, str]:
    return {
        "name": f"user-{suffix}",
        "email": f"auth-{suffix}@email.com",
        "password": password,
    }


def test_register_duplicate_email_returns_409(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)

    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409
    assert second.get_json()["message"] == "Email already registered"


def test_register_with_weak_password_returns_400(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix, password="123")

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert "message" in body
    assert "errors" in body


def test_login_with_name_and_logout_success(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    login = client.post(
        "/auth/login",
        json={
            "name": payload["name"],
            "password": payload["password"],
        },
    )
    assert login.status_code == 200
    token = login.get_json()["token"]

    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 200
    assert logout.get_json()["message"] == "Logout successful"


def test_login_with_invalid_credentials_returns_401(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    response = client.post(
        "/auth/login",
        json={
            "email": payload["email"],
            "password": "WrongPass@123",
        },
    )

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid credentials"
