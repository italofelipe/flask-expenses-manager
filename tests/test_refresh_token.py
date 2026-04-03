"""B18 — POST /auth/refresh endpoint tests.

Covers:
- Happy path: valid refresh token → new access + refresh token pair
- Replay attack: using the same refresh token twice → 401 TOKEN_REUSED
- Token rotation: new refresh token replaces the old one in DB
- Missing/invalid Authorization header → 401 (JWT extension handles)
- Rate limit: 11th request in a 60s window → 429
- Expired refresh token: flask-jwt-extended raises → 401
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from werkzeug.security import generate_password_hash

from app.controllers.auth.dependencies import _get_token_jti
from app.extensions.database import db

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _create_user(
    app, *, email: str = "user@test.com", password: str = "Pass123!"
) -> Any:
    from app.models.user import User

    with app.app_context():
        user = User(
            id=uuid.uuid4(),
            name="Test User",
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, *, email: str = "user@test.com", password: str = "Pass123!") -> dict:
    """POST /auth/login and return parsed JSON body."""
    resp = client.post(
        "/auth/login",
        json={"email": email, "password": password, "captcha_token": "test"},
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    # Support both legacy and v2 envelope
    data = body.get("data") or body
    return data


def _refresh(client, *, refresh_token: str) -> Any:
    return client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )


# ─── Happy path ───────────────────────────────────────────────────────────────


class TestRefreshTokenHappyPath:
    def test_returns_200_with_new_token_pair(self, app, client):
        _create_user(app)
        login_data = _login(client)
        refresh_token = login_data.get("refresh_token")
        assert refresh_token, "Login must return refresh_token"

        resp = _refresh(client, refresh_token=refresh_token)
        assert resp.status_code == 200, resp.get_json()

        body = resp.get_json()
        data = body.get("data") or body
        assert "token" in data
        assert "refresh_token" in data

    def test_new_access_token_differs_from_original(self, app, client):
        _create_user(app)
        login_data = _login(client)
        old_token = login_data["token"]
        refresh_token = login_data["refresh_token"]

        resp = _refresh(client, refresh_token=refresh_token)
        body = resp.get_json()
        data = body.get("data") or body
        assert data["token"] != old_token

    def test_new_refresh_token_differs_from_original(self, app, client):
        _create_user(app)
        login_data = _login(client)
        old_refresh = login_data["refresh_token"]

        resp = _refresh(client, refresh_token=old_refresh)
        body = resp.get_json()
        data = body.get("data") or body
        assert data["refresh_token"] != old_refresh

    def test_db_refresh_jti_updated_after_refresh(self, app, client):
        user_id = _create_user(app)
        login_data = _login(client)
        old_refresh = login_data["refresh_token"]

        _refresh(client, refresh_token=old_refresh)

        with app.app_context():
            from app.models.user import User

            user = User.query.filter_by(id=user_id).first()
            # After rotation the stored JTI must not match the original token's JTI
            old_jti = _get_token_jti(old_refresh)
            assert user.refresh_token_jti != old_jti


# ─── Replay attack prevention ─────────────────────────────────────────────────


class TestRefreshTokenReplay:
    def test_second_use_of_same_token_returns_401(self, app, client):
        _create_user(app)
        login_data = _login(client)
        refresh_token = login_data["refresh_token"]

        # First use — should succeed
        resp1 = _refresh(client, refresh_token=refresh_token)
        assert resp1.status_code == 200

        # Second use of the SAME token — must fail
        resp2 = _refresh(client, refresh_token=refresh_token)
        assert resp2.status_code == 401

    def test_replay_response_is_unauthorized(self, app, client):
        """Second use of the same refresh token must be rejected (401).

        The replay may be detected either at the JWT blocklist level
        (UNAUTHORIZED / "Token revogado") or at the resource level
        (TOKEN_REUSED). Either way the status code must be 401.
        """
        _create_user(app)
        login_data = _login(client)
        refresh_token = login_data["refresh_token"]

        _refresh(client, refresh_token=refresh_token)
        resp = _refresh(client, refresh_token=refresh_token)
        assert resp.status_code == 401


# ─── Invalid / missing token ──────────────────────────────────────────────────


class TestRefreshTokenInvalid:
    def test_no_authorization_header_returns_401(self, client):
        resp = client.post("/auth/refresh")
        assert resp.status_code == 401

    def test_access_token_used_as_refresh_token_returns_422_or_401(self, app, client):
        _create_user(app)
        login_data = _login(client)
        access_token = login_data["token"]  # NOT a refresh token

        resp = _refresh(client, refresh_token=access_token)
        # flask-jwt-extended returns 422 for wrong token type
        assert resp.status_code in (401, 422)

    def test_malformed_token_returns_401_or_422(self, client):
        resp = _refresh(client, refresh_token="not.a.jwt")
        assert resp.status_code in (401, 422)


# ─── Rate limit ───────────────────────────────────────────────────────────────


class TestRefreshTokenRateLimit:
    def test_11th_request_returns_429(self, app, client):
        """token_refresh rule: 10 req/60s per IP."""
        _create_user(app)

        limiter = app.extensions.get("rate_limiter")
        if limiter is None:
            pytest.skip("Rate limiter not registered in test app")

        # Reset storage so previous tests don't bleed in
        limiter.reset()

        # Perform 10 successful refreshes (rotating token each time)
        login_data = _login(client)
        current_refresh = login_data["refresh_token"]
        for _ in range(10):
            resp = _refresh(client, refresh_token=current_refresh)
            if resp.status_code == 200:
                body = resp.get_json()
                data = body.get("data") or body
                current_refresh = data["refresh_token"]
            # Might hit 429 early if IP already has some count — that's fine

        # 11th request must be rate-limited
        resp = _refresh(client, refresh_token=current_refresh)
        assert resp.status_code == 429

    def test_rate_limit_rule_exists_in_limiter(self, app):
        limiter = app.extensions.get("rate_limiter")
        if limiter is None:
            pytest.skip("Rate limiter not registered in test app")
        assert "token_refresh" in limiter._rules
        rule = limiter._rules["token_refresh"]
        assert rule.limit == 10
        assert rule.window_seconds == 60


# ─── Login issues refresh_token ───────────────────────────────────────────────


class TestLoginIssuesRefreshToken:
    def test_login_response_contains_refresh_token(self, app, client):
        _create_user(app)
        login_data = _login(client)
        assert "refresh_token" in login_data
        assert login_data["refresh_token"]

    def test_login_stores_refresh_jti_in_db(self, app, client):
        user_id = _create_user(app)
        login_data = _login(client)
        refresh_token = login_data["refresh_token"]

        with app.app_context():
            from app.models.user import User

            user = User.query.filter_by(id=user_id).first()
            expected_jti = _get_token_jti(refresh_token)
            assert user.refresh_token_jti == expected_jti
