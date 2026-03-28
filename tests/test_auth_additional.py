import uuid

from app.controllers.auth.dependencies import AuthDependencies
from app.controllers.auth.login_resource import AuthResource
from app.models.user import User


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


def test_login_with_email_and_logout_success(client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = _register_payload(suffix)
    register = client.post("/auth/register", json=payload)
    assert register.status_code == 201

    login = client.post(
        "/auth/login",
        json={
            "email": payload["email"],
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


def test_login_resource_missing_credentials_branch_returns_validation_error(
    app,
) -> None:
    with app.test_request_context(
        "/auth/login",
        method="POST",
        headers={"X-API-Contract": "v2"},
    ):
        response = AuthResource.post.__wrapped__(
            AuthResource(),
            email="",
            password="StrongPass@123",
        )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_login_resource_unexpected_failure_returns_internal_error(
    app,
    monkeypatch,
) -> None:
    user = User(
        name="auth-crash-user",
        email="auth-crash@email.com",
        password="hashed-password",
    )
    dependencies = AuthDependencies(
        get_auth_security_policy=lambda: type(
            "Policy",
            (),
            {
                "login_guard": type(
                    "LoginGuardPolicy",
                    (),
                    {"expose_known_principal": False},
                )()
            },
        )(),
        get_login_attempt_guard=lambda: object(),
        build_login_attempt_context=lambda **_kwargs: object(),
        verify_password=lambda _password_hash, _plain_password: True,
        hash_password=lambda plain_password: plain_password,
        create_access_token=lambda _identity: (_ for _ in ()).throw(
            RuntimeError("token creation failed")
        ),
        get_token_jti=lambda token: token,
        find_user_by_email=lambda _email: user,
        get_user_by_id=lambda _user_id: None,
        request_password_reset=lambda _email: None,
        reset_password=lambda _token, _password_hash: None,
    )
    monkeypatch.setattr(
        "app.controllers.auth.login_resource.guard_login_check",
        lambda **_kwargs: (True, 0),
    )
    monkeypatch.setattr(
        "app.controllers.auth.login_resource.guard_register_success",
        lambda **_kwargs: None,
    )

    monkeypatch.setattr(
        "app.controllers.auth.login_resource.get_auth_dependencies",
        lambda: dependencies,
    )

    with app.test_request_context(
        "/auth/login",
        method="POST",
        headers={"X-API-Contract": "v2"},
    ):
        response = AuthResource.post.__wrapped__(
            AuthResource(),
            email="auth-crash@email.com",
            password="StrongPass@123",
        )

    assert response.status_code == 500
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
