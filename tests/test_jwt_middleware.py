from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from flask import Flask, jsonify, request

from app.middleware.jwt import token_required


def _build_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "super-secret-key-for-tests-only-with-32-plus-chars"
    return app


def test_token_required_rejects_missing_authorization_header() -> None:
    app = _build_app()

    @token_required
    def protected() -> tuple[dict[str, str], int]:
        return {"ok": "true"}, 200

    with app.test_request_context("/protected"):
        response = protected()

    assert response.status_code == 401
    assert response.get_json()["message"] == "Token is missing!"


def test_token_required_rejects_expired_token() -> None:
    app = _build_app()

    @token_required
    def protected() -> tuple[dict[str, str], int]:
        return {"ok": "true"}, 200

    expired_token = jwt.encode(
        {
            "user_id": "user-1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    with app.test_request_context(
        "/protected", headers={"Authorization": f"Bearer {expired_token}"}
    ):
        response = protected()

    assert response.status_code == 401
    assert response.get_json()["message"] == "Token expired!"


def test_token_required_rejects_invalid_token() -> None:
    app = _build_app()

    @token_required
    def protected() -> tuple[dict[str, str], int]:
        return {"ok": "true"}, 200

    with app.test_request_context(
        "/protected", headers={"Authorization": "Bearer invalid.token.value"}
    ):
        response = protected()

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid token!"


def test_token_required_sets_request_user_id_and_calls_wrapped_function() -> None:
    app = _build_app()

    @token_required
    def protected() -> tuple[dict[str, str], int]:
        return {"user_id": request.environ.get("auraxis.user_id", "")}, 200

    token = jwt.encode(
        {
            "user_id": "user-123",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    with app.test_request_context(
        "/protected", headers={"Authorization": f"Bearer {token}"}
    ):
        payload, status = protected()
        response = jsonify(payload)
        response.status_code = status

    assert response.status_code == 200
    assert response.get_json()["user_id"] == "user-123"
