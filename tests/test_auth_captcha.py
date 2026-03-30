"""Tests for Cloudflare Turnstile CAPTCHA verification on auth endpoints.

Covers:
- CaptchaService unit tests (disabled, missing token, valid, invalid, network error)
- Integration: register and login return 400 when CAPTCHA is enabled and token fails
- Integration: register and login succeed when CAPTCHA is disabled (dev mode)
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.captcha_service import CaptchaService

# ---------------------------------------------------------------------------
# CaptchaService unit tests
# ---------------------------------------------------------------------------


class TestCaptchaServiceDisabled:
    def test_verify_returns_true_when_disabled(self) -> None:
        svc = CaptchaService(secret_key="secret", enabled=False)
        assert svc.verify("any-token") is True

    def test_verify_returns_true_when_no_secret_key(self) -> None:
        svc = CaptchaService(secret_key="", enabled=True)
        assert svc.verify("any-token") is True

    def test_verify_returns_true_when_no_secret_key_and_no_token(self) -> None:
        svc = CaptchaService(secret_key="", enabled=True)
        assert svc.verify(None) is True


class TestCaptchaServiceEnabled:
    def test_verify_returns_false_when_token_is_none(self) -> None:
        svc = CaptchaService(secret_key="secret", enabled=True)
        assert svc.verify(None) is False

    def test_verify_returns_false_when_token_is_empty_string(self) -> None:
        svc = CaptchaService(secret_key="secret", enabled=True)
        assert svc.verify("") is False

    def test_verify_returns_true_on_cloudflare_success(self, app) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None

        with app.app_context():
            with patch(
                "app.services.captcha_service.requests.post", return_value=mock_response
            ):
                svc = CaptchaService(secret_key="secret", enabled=True)
                result = svc.verify("valid-token")

        assert result is True

    def test_verify_returns_false_on_cloudflare_rejection(self, app) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"],
        }
        mock_response.raise_for_status.return_value = None

        with app.app_context():
            with patch(
                "app.services.captcha_service.requests.post", return_value=mock_response
            ):
                svc = CaptchaService(secret_key="secret", enabled=True)
                result = svc.verify("invalid-token")

        assert result is False

    def test_verify_fails_open_on_network_error(self, app) -> None:
        """When Cloudflare is unreachable, allow the request (fail-open)."""
        from requests.exceptions import ConnectionError as ReqConnectionError

        with app.app_context():
            with patch(
                "app.services.captcha_service.requests.post",
                side_effect=ReqConnectionError("timeout"),
            ):
                svc = CaptchaService(secret_key="secret", enabled=True)
                result = svc.verify("some-token")

        assert result is True


# ---------------------------------------------------------------------------
# Integration: CAPTCHA disabled (default test env — no secret key configured)
# ---------------------------------------------------------------------------


def _reg_payload(suffix: str) -> dict[str, str]:
    return {
        "name": f"captcha-user-{suffix}",
        "email": f"captcha-{suffix}@test.com",
        "password": "StrongPass@123",
    }


def test_register_succeeds_without_captcha_token_when_disabled(client) -> None:
    """Default test environment has no secret key → CAPTCHA disabled → 201."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post("/auth/register", json=_reg_payload(suffix))
    assert resp.status_code == 201


def test_login_succeeds_without_captcha_token_when_disabled(client) -> None:
    """Default test environment has no secret key → CAPTCHA disabled → 200."""
    suffix = uuid.uuid4().hex[:8]
    payload = _reg_payload(suffix)
    client.post("/auth/register", json=payload)

    resp = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Integration: CAPTCHA enabled (secret key patched into app config)
# ---------------------------------------------------------------------------


@pytest.fixture()
def captcha_app(app):
    """App fixture with Turnstile secret key configured (CAPTCHA enabled)."""
    app.config["CLOUDFLARE_TURNSTILE_SECRET_KEY"] = "test-secret"
    app.config["CLOUDFLARE_TURNSTILE_ENABLED"] = True
    return app


@pytest.fixture()
def captcha_client(captcha_app):
    return captcha_app.test_client()


_V2_HEADERS = {"X-API-Contract": "v2"}


def _mock_turnstile(success: bool):
    """Return a context-manager patch that fakes the Cloudflare response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"success": success}
    mock_resp.raise_for_status.return_value = None
    return patch("app.services.captcha_service.requests.post", return_value=mock_resp)


def test_register_blocked_when_captcha_missing_and_enabled(captcha_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    with _mock_turnstile(False):
        resp = captcha_client.post(
            "/auth/register", json=_reg_payload(suffix), headers=_V2_HEADERS
        )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "CAPTCHA_INVALID"


def test_register_blocked_when_captcha_invalid_and_enabled(captcha_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = {**_reg_payload(suffix), "captcha_token": "bad-token"}
    with _mock_turnstile(False):
        resp = captcha_client.post("/auth/register", json=payload, headers=_V2_HEADERS)
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "CAPTCHA_INVALID"


def test_register_succeeds_when_captcha_valid_and_enabled(
    captcha_client, captcha_app
) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = {**_reg_payload(suffix), "captcha_token": "valid-token"}
    with _mock_turnstile(True):
        resp = captcha_client.post("/auth/register", json=payload)
    assert resp.status_code == 201


def test_login_blocked_when_captcha_missing_and_enabled(
    captcha_client, captcha_app
) -> None:
    # First register without CAPTCHA (disabled during setup)
    suffix = uuid.uuid4().hex[:8]
    reg_payload = _reg_payload(suffix)
    captcha_app.config["CLOUDFLARE_TURNSTILE_SECRET_KEY"] = ""
    captcha_client.post("/auth/register", json=reg_payload)
    captcha_app.config["CLOUDFLARE_TURNSTILE_SECRET_KEY"] = "test-secret"

    with _mock_turnstile(False):
        resp = captcha_client.post(
            "/auth/login",
            json={"email": reg_payload["email"], "password": reg_payload["password"]},
            headers=_V2_HEADERS,
        )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "CAPTCHA_INVALID"


def test_login_succeeds_when_captcha_valid_and_enabled(
    captcha_client, captcha_app
) -> None:
    suffix = uuid.uuid4().hex[:8]
    reg_payload = _reg_payload(suffix)
    # Register with CAPTCHA disabled
    captcha_app.config["CLOUDFLARE_TURNSTILE_SECRET_KEY"] = ""
    captcha_client.post("/auth/register", json=reg_payload)
    captcha_app.config["CLOUDFLARE_TURNSTILE_SECRET_KEY"] = "test-secret"

    login_payload = {
        "email": reg_payload["email"],
        "password": reg_payload["password"],
        "captcha_token": "valid-token",
    }
    with _mock_turnstile(True):
        resp = captcha_client.post("/auth/login", json=login_payload)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Schema-level: camelCase normalization (TypeScript frontend sends captchaToken)
# ---------------------------------------------------------------------------


class TestAuthSchemaCamelCaseNormalization:
    """AuthSchema pre_load must accept captchaToken (camelCase) from TS clients."""

    def test_login_schema_normalizes_camelcase_captcha_token(self) -> None:
        from app.schemas.auth_schema import AuthSchema

        schema = AuthSchema()
        result = schema.sanitize_input(
            {"email": "TEST@EXAMPLE.COM", "password": "pass", "captchaToken": "tok123"},
        )
        assert isinstance(result, dict)
        assert result["captcha_token"] == "tok123"
        assert "captchaToken" not in result
        assert result["email"] == "test@example.com"

    def test_login_schema_snake_case_token_is_not_renamed(self) -> None:
        from app.schemas.auth_schema import AuthSchema

        schema = AuthSchema()
        result = schema.sanitize_input(
            {"email": "a@b.com", "password": "p", "captcha_token": "tok"},
        )
        assert isinstance(result, dict)
        assert result["captcha_token"] == "tok"
        assert "captchaToken" not in result

    def test_login_schema_non_dict_input_passes_through(self) -> None:
        from app.schemas.auth_schema import AuthSchema

        schema = AuthSchema()
        # sanitize_string_fields may return non-dict for non-dict raw input;
        # the guard must return it unchanged so Marshmallow can raise its own error.
        result = schema.sanitize_input(None)
        assert result is None

    def test_register_schema_normalizes_camelcase_captcha_token(self) -> None:
        from app.schemas.user_schemas import UserRegistrationSchema

        schema = UserRegistrationSchema()
        result = schema.sanitize_input(
            {
                "name": "  Alice  ",
                "email": "ALICE@EXAMPLE.COM",
                "password": "Secret@1234",
                "captchaToken": "reg-tok",
            },
        )
        assert isinstance(result, dict)
        assert result["captcha_token"] == "reg-tok"
        assert "captchaToken" not in result
        assert result["email"] == "alice@example.com"

    def test_register_schema_non_dict_input_passes_through(self) -> None:
        from app.schemas.user_schemas import UserRegistrationSchema

        schema = UserRegistrationSchema()
        result = schema.sanitize_input(None)
        assert result is None
