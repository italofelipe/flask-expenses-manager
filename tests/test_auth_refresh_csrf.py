"""SEC-AUD-03 — CSRF double-submit protection for the refresh cookie.

Covers the two-phase rollout gated by AURAXIS_CSRF_ENFORCE
(exposed as the Flask config ``JWT_COOKIE_CSRF_PROTECT``):

Phase 1 (flag OFF — current default, backward compatible):
- No CSRF cookie is set on login.
- ``POST /auth/refresh`` succeeds without ``X-CSRF-TOKEN`` header.

Phase 2 (flag ON — after clients migrate):
- Login sets the ``auraxis_csrf_refresh`` cookie (non-HttpOnly so JS can read).
- Refresh without a matching ``X-CSRF-TOKEN`` header returns 401.
- Refresh succeeds when the header value matches the cookie value.
- Rotation also rotates the CSRF token.
"""

from __future__ import annotations

import uuid
from typing import Any

from werkzeug.security import generate_password_hash

from app.extensions.database import db

REFRESH_COOKIE_NAME = "auraxis_refresh"
CSRF_REFRESH_COOKIE_NAME = "auraxis_csrf_refresh"


def _create_user(
    app, *, email: str = "csrf@test.com", password: str = "Pass123!"
) -> Any:
    from app.models.user import User

    with app.app_context():
        user = User(
            id=uuid.uuid4(),
            name="CSRF Test User",
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, *, email: str = "csrf@test.com", password: str = "Pass123!"):
    return client.post(
        "/auth/login",
        json={"email": email, "password": password, "captcha_token": "test"},
    )


def _find_set_cookie(response, name: str) -> str | None:
    for header_name, header_value in response.headers.items():
        if header_name.lower() != "set-cookie":
            continue
        if header_value.split("=", 1)[0].strip() == name:
            return header_value
    return None


def _cookie_value(raw: str) -> str:
    return raw.split("=", 1)[1].split(";", 1)[0]


# ─── Phase 1 — default OFF (backward compatible) ─────────────────────────────


class TestCsrfDisabledByDefault:
    def test_login_does_not_set_csrf_cookie_when_flag_off(self, app, client):
        _create_user(app, email="csrf-off-login@test.com")
        resp = _login(client, email="csrf-off-login@test.com")
        assert resp.status_code == 200, resp.get_json()
        assert _find_set_cookie(resp, CSRF_REFRESH_COOKIE_NAME) is None

    def test_refresh_succeeds_without_csrf_header_when_flag_off(self, app, client):
        _create_user(app, email="csrf-off-refresh@test.com")
        _login(client, email="csrf-off-refresh@test.com")
        resp = client.post("/auth/refresh")
        assert resp.status_code == 200, resp.get_json()


# ─── Phase 2 — enforcement ON ────────────────────────────────────────────────


class TestCsrfEnforcementWhenEnabled:
    def _enable_csrf(self, app) -> None:
        app.config["JWT_COOKIE_CSRF_PROTECT"] = True

    def test_login_sets_csrf_refresh_cookie(self, app, client):
        self._enable_csrf(app)
        _create_user(app, email="csrf-on-login@test.com")
        resp = _login(client, email="csrf-on-login@test.com")
        assert resp.status_code == 200, resp.get_json()
        raw = _find_set_cookie(resp, CSRF_REFRESH_COOKIE_NAME)
        assert raw is not None, "login must emit Set-Cookie auraxis_csrf_refresh"

    def test_csrf_cookie_is_not_http_only(self, app, client):
        """JS on the client needs to read the cookie to forward it as a header."""
        self._enable_csrf(app)
        _create_user(app, email="csrf-on-not-httponly@test.com")
        resp = _login(client, email="csrf-on-not-httponly@test.com")
        raw = _find_set_cookie(resp, CSRF_REFRESH_COOKIE_NAME) or ""
        assert raw, "CSRF cookie must be emitted"
        assert "HttpOnly" not in raw, "CSRF cookie must be readable by client JS"

    def test_refresh_without_csrf_header_returns_401(self, app, client):
        self._enable_csrf(app)
        _create_user(app, email="csrf-on-missing-header@test.com")
        _login(client, email="csrf-on-missing-header@test.com")
        resp = client.post("/auth/refresh")
        assert resp.status_code == 401, resp.get_json()

    def test_refresh_with_matching_csrf_header_succeeds(self, app, client):
        self._enable_csrf(app)
        _create_user(app, email="csrf-on-matching@test.com")
        login_resp = _login(client, email="csrf-on-matching@test.com")
        csrf_raw = _find_set_cookie(login_resp, CSRF_REFRESH_COOKIE_NAME)
        assert csrf_raw is not None
        csrf_value = _cookie_value(csrf_raw)

        resp = client.post("/auth/refresh", headers={"X-CSRF-TOKEN": csrf_value})
        assert resp.status_code == 200, resp.get_json()

    def test_refresh_with_wrong_csrf_header_returns_401(self, app, client):
        self._enable_csrf(app)
        _create_user(app, email="csrf-on-wrong@test.com")
        _login(client, email="csrf-on-wrong@test.com")
        resp = client.post(
            "/auth/refresh",
            headers={"X-CSRF-TOKEN": "tampered-value-does-not-match-cookie"},
        )
        assert resp.status_code == 401, resp.get_json()

    def test_refresh_rotates_csrf_cookie(self, app, client):
        self._enable_csrf(app)
        _create_user(app, email="csrf-on-rotate@test.com")
        login_resp = _login(client, email="csrf-on-rotate@test.com")
        original_raw = _find_set_cookie(login_resp, CSRF_REFRESH_COOKIE_NAME)
        assert original_raw is not None
        original_value = _cookie_value(original_raw)

        refresh_resp = client.post(
            "/auth/refresh", headers={"X-CSRF-TOKEN": original_value}
        )
        assert refresh_resp.status_code == 200, refresh_resp.get_json()

        rotated_raw = _find_set_cookie(refresh_resp, CSRF_REFRESH_COOKIE_NAME)
        assert rotated_raw is not None, "refresh must rotate the CSRF cookie"
        rotated_value = _cookie_value(rotated_raw)
        assert rotated_value != original_value, (
            "rotated CSRF token must differ from the original"
        )
