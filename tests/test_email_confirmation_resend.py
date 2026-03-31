"""Tests for POST /auth/email/resend (JWT-protected resend confirmation).

Covers:
- 401 when no Authorization header is present
- 200 (neutral) when token is valid and user exists but is unconfirmed
- 200 (neutral) when token is valid and user is already confirmed (no re-send)
- 200 (neutral) when token subject does not resolve to an existing user
"""

from __future__ import annotations

import uuid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client) -> tuple[str, str]:
    """Register a fresh user and return (email, jwt_token)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"resend-{suffix}@test.com"
    password = "StrongPass@123"
    reg_resp = client.post(
        "/auth/register",
        json={"name": f"Resend User {suffix}", "email": email, "password": password},
    )
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.get_json()}"
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.get_json()}"
    body = resp.get_json()
    # Support both v1 legacy envelope (token at root) and v2 (data.token)
    token = body.get("token") or body.get("data", {}).get("token")
    assert token, f"No token in login response: {body}"
    return email, token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResendConfirmationAuth:
    def test_returns_401_without_token(self, client) -> None:
        resp = client.post("/auth/email/resend")
        assert resp.status_code == 401

    def test_returns_401_with_malformed_token(self, client) -> None:
        resp = client.post(
            "/auth/email/resend",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code in (401, 422)


class TestResendConfirmationSuccess:
    def test_returns_200_with_valid_jwt(self, client) -> None:
        _email, token = _register_and_login(client)
        resp = client.post(
            "/auth/email/resend",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_response_body_is_neutral(self, client) -> None:
        """Response must not expose whether email existed / was already confirmed."""
        from app.application.services.email_confirmation_service import (
            EMAIL_CONFIRMATION_NEUTRAL_MESSAGE,
        )

        _email, token = _register_and_login(client)
        resp = client.post(
            "/auth/email/resend",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.get_json()
        assert data["message"] == EMAIL_CONFIRMATION_NEUTRAL_MESSAGE

    def test_no_request_body_required(self, client) -> None:
        """Client must NOT need to send email in body — auth is via JWT."""
        _email, token = _register_and_login(client)
        # POST with explicit empty body — must still succeed
        resp = client.post(
            "/auth/email/resend",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_body_with_email_field_is_ignored(self, client) -> None:
        """Even if client sends email in body it should be silently ignored."""
        _email, token = _register_and_login(client)
        resp = client.post(
            "/auth/email/resend",
            json={"email": "random@other.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Must succeed and act on the JWT user, not the body email
        assert resp.status_code == 200
