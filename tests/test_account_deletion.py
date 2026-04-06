"""Tests for DELETE /user/me — LGPD-compliant account deletion (issue #885)."""

from __future__ import annotations

import uuid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASSWORD = "StrongPass@123"


def _register_and_login(client, *, password: str = _PASSWORD) -> tuple[str, str]:
    """Register a fresh user, log in, and return (token, email)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"del-{suffix}@email.com"

    reg = client.post(
        "/auth/register",
        json={"name": f"del-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201, reg.get_json()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.get_json()
    return login.get_json()["token"], email


def _delete_me(client, token: str, password: str = _PASSWORD):
    return client.delete(
        "/user/me",
        json={"password": password},
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_delete_me_returns_200(client) -> None:
    token, _ = _register_and_login(client)
    resp = _delete_me(client, token)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["message"] == "Account deleted."
    assert body["success"] is True


def test_delete_me_anonymises_pii(client, app) -> None:
    from app.models.user import User

    token, email = _register_and_login(client)
    _delete_me(client, token)

    with app.app_context():
        user = User.query.filter(User.email.like("deleted_%@deleted.auraxis")).first()
        assert user is not None, "No anonymised user found"
        assert user.name == "Deleted User"
        assert user.email.startswith("deleted_")
        assert user.email.endswith("@deleted.auraxis")
        assert user.birth_date is None
        assert user.state_uf is None
        assert user.occupation is None
        assert user.gender is None
        assert float(user.monthly_income_net or 0) == 0
        assert float(user.monthly_expenses or 0) == 0
        assert float(user.net_worth or 0) == 0
        assert user.deleted_at is not None


def test_delete_me_revokes_jwt(client) -> None:
    token, _ = _register_and_login(client)
    _delete_me(client, token)

    # Subsequent request with the same token must be rejected.
    follow_up = client.get(
        "/user/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert follow_up.status_code == 401


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_delete_me_wrong_password_returns_403(client) -> None:
    token, _ = _register_and_login(client)
    resp = _delete_me(client, token, password="WrongPassword@999")
    assert resp.status_code == 403
    body = resp.get_json()
    # Legacy envelope: {"message": "Invalid credentials."}
    # v2/v3 envelope: {"error": {"code": "INVALID_CREDENTIALS"}}
    error_code = (body.get("error") or {}).get("code", "")
    message = body.get("message", "")
    assert error_code == "INVALID_CREDENTIALS" or "Invalid credentials" in message


def test_delete_me_missing_password_returns_4xx(client) -> None:
    token, _ = _register_and_login(client)
    resp = client.delete(
        "/user/me",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    # flask-apispec use_kwargs returns 400 or 422 for missing required fields.
    assert resp.status_code in (400, 422)


def test_delete_me_unauthenticated_returns_401(client) -> None:
    resp = client.delete(
        "/user/me",
        json={"password": _PASSWORD},
    )
    assert resp.status_code == 401


def test_delete_me_already_deleted_rejects_second_attempt(client) -> None:
    token, _ = _register_and_login(client)
    first = _delete_me(client, token)
    assert first.status_code == 200

    # Second attempt with the same (now revoked) token must fail.
    second = _delete_me(client, token)
    assert second.status_code == 401
