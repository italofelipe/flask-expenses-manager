from __future__ import annotations

from flask_jwt_extended.exceptions import NoAuthorizationError

from app.middleware import auth_guard as auth_guard_module


def test_auth_guard_returns_401_for_expected_jwt_errors(client, monkeypatch) -> None:
    def _raise_jwt_error() -> None:
        raise NoAuthorizationError("missing authorization header")

    monkeypatch.setattr(auth_guard_module, "verify_jwt_in_request", _raise_jwt_error)

    response = client.get("/user/me")

    assert response.status_code == 401
    assert response.get_json()["message"] == "Token inválido ou ausente"


def test_auth_guard_returns_500_for_unexpected_errors(client, monkeypatch) -> None:
    def _raise_runtime_error() -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(
        auth_guard_module, "verify_jwt_in_request", _raise_runtime_error
    )

    response = client.get("/user/me")

    assert response.status_code == 500
    assert response.get_json()["message"] == "Internal Server Error"
