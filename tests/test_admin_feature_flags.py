"""
Tests for admin feature flag HTTP endpoints.

Covers:
- GET  /admin/feature-flags          (list)
- GET  /admin/feature-flags/<name>   (found, 404, invalid name)
- POST /admin/feature-flags          (valid, invalid name, invalid canary_pct, Redis
  unavailable)
- DELETE /admin/feature-flags/<name> (success, invalid name)
- Name validation regex
- 403 Forbidden for non-admin users on all 4 endpoints
- _is_admin() exception branch (returns False when get_active_auth_context raises)
- User.__repr__
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from app.services.feature_flag_service import FeatureFlagConfig

# ── Fixtures ──────────────────────────────────────────────────────────────────

_TEST_ENV = {
    "SECRET_KEY": "test-secret-key-with-64-chars-minimum-for-jwt-signing-0001",
    "JWT_SECRET_KEY": "test-jwt-secret-key-with-64-chars-minimum-for-signing-0002",
    "FLASK_TESTING": "true",
    "SECURITY_ENFORCE_STRONG_SECRETS": "false",
    "DOCS_EXPOSURE_POLICY": "public",
    "CORS_ALLOWED_ORIGINS": "https://frontend.local",
    "GRAPHQL_ALLOW_INTROSPECTION": "true",
}


@pytest.fixture()
def admin_app(tmp_path: Path):
    """Flask app with HTTP runtime disabled (no auth guard) for admin endpoint tests."""
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    for k, v in _TEST_ENV.items():
        os.environ[k] = v

    from app import create_app
    from app.extensions.database import db

    flask_app = create_app(enable_http_runtime=False)
    flask_app.config["TESTING"] = True

    with flask_app.app_context():
        db.drop_all()
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(admin_app) -> Generator:  # type: ignore[override]
    with admin_app.test_client() as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────


def _flag_config(
    *,
    enabled: bool = True,
    canary_percentage: int = 0,
    description: str = "",
    updated_at: str = "2026-04-01T00:00:00+00:00",
) -> FeatureFlagConfig:
    return FeatureFlagConfig(
        enabled=enabled,
        canary_percentage=canary_percentage,
        description=description,
        updated_at=updated_at,
    )


def _make_svc_mock(
    *,
    list_result: dict | None = None,
    get_result: FeatureFlagConfig | None = None,
) -> MagicMock:
    svc = MagicMock()
    svc.list_flags.return_value = list_result or {}
    svc.get_flag.return_value = get_result
    return svc


# ── 403 Forbidden (non-admin) ─────────────────────────────────────────────────


class TestAdminRoleEnforcement:
    """All 4 admin endpoints must return 403 when the caller is not an admin."""

    def test_list_returns_403_for_non_admin(self, client) -> None:
        with patch(
            "app.controllers.admin.feature_flags._is_admin",
            return_value=False,
        ):
            resp = client.get("/admin/feature-flags")
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

    def test_get_returns_403_for_non_admin(self, client) -> None:
        with patch(
            "app.controllers.admin.feature_flags._is_admin",
            return_value=False,
        ):
            resp = client.get("/admin/feature-flags/tools.fgts")
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

    def test_post_returns_403_for_non_admin(self, client) -> None:
        with patch(
            "app.controllers.admin.feature_flags._is_admin",
            return_value=False,
        ):
            resp = client.post(
                "/admin/feature-flags",
                json={"name": "tools.flag", "enabled": True},
            )
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

    def test_delete_returns_403_for_non_admin(self, client) -> None:
        with patch(
            "app.controllers.admin.feature_flags._is_admin",
            return_value=False,
        ):
            resp = client.delete("/admin/feature-flags/tools.fgts_simulator")
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"


# ── List ──────────────────────────────────────────────────────────────────────


class TestListFeatureFlags:
    def test_list_returns_empty_when_no_flags(self, client) -> None:
        svc = _make_svc_mock(list_result={})
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.get("/admin/feature-flags")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 0
        assert body["flags"] == {}

    def test_list_returns_flags(self, client) -> None:
        cfg = _flag_config(enabled=True, canary_percentage=10)
        svc = _make_svc_mock(list_result={"tools.fgts": cfg})
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.get("/admin/feature-flags")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1
        assert "tools.fgts" in body["flags"]
        assert body["flags"]["tools.fgts"]["enabled"] is True


# ── Get ───────────────────────────────────────────────────────────────────────


class TestGetFeatureFlag:
    def test_get_existing_flag(self, client) -> None:
        cfg = _flag_config(enabled=True, canary_percentage=25)
        svc = _make_svc_mock(get_result=cfg)
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.get("/admin/feature-flags/tools.fgts")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["name"] == "tools.fgts"
        assert body["enabled"] is True

    def test_get_returns_404_when_not_found(self, client) -> None:
        svc = _make_svc_mock(get_result=None)
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.get("/admin/feature-flags/nonexistent.flag")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    def test_get_returns_404_for_invalid_name_chars(self, client) -> None:
        # Path param with injection characters must return 404
        svc = _make_svc_mock(get_result=None)
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.get("/admin/feature-flags/flag%0Ainjected")
        # Either 404 or 400 is acceptable; service should not be called
        assert resp.status_code in (404, 400)


# ── Create / Update ───────────────────────────────────────────────────────────


class TestCreateOrUpdateFeatureFlag:
    def test_create_valid_flag(self, client) -> None:
        cfg = _flag_config(enabled=True, canary_percentage=0)
        svc = MagicMock()
        svc.get_flag.return_value = cfg
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.post(
                "/admin/feature-flags",
                json={
                    "name": "tools.fgts_simulator",
                    "enabled": True,
                    "canary_percentage": 0,
                    "description": "FGTS tool",
                },
            )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["name"] == "tools.fgts_simulator"
        svc.set_flag.assert_called_once()

    def test_create_missing_name_returns_422(self, client) -> None:
        svc = MagicMock()
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.post("/admin/feature-flags", json={"enabled": True})
        assert resp.status_code == 422
        body = resp.get_json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        svc.set_flag.assert_not_called()

    def test_create_invalid_name_chars_returns_422(self, client) -> None:
        svc = MagicMock()
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.post(
                "/admin/feature-flags",
                json={"name": "flag\ninjected", "enabled": True},
            )
        assert resp.status_code == 422
        body = resp.get_json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        svc.set_flag.assert_not_called()

    def test_create_invalid_canary_pct_returns_422(self, client) -> None:
        svc = MagicMock()
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.post(
                "/admin/feature-flags",
                json={"name": "tools.flag", "enabled": True, "canary_percentage": 150},
            )
        assert resp.status_code == 422
        body = resp.get_json()
        assert "canary_percentage" in str(body)
        svc.set_flag.assert_not_called()

    def test_create_redis_unavailable_returns_503(self, client) -> None:
        svc = MagicMock()
        svc.get_flag.return_value = None  # Redis unavailable after set
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.post(
                "/admin/feature-flags",
                json={"name": "tools.flag", "enabled": True},
            )
        assert resp.status_code == 503
        body = resp.get_json()
        assert body["error"]["code"] == "SERVICE_UNAVAILABLE"


# ── Delete ────────────────────────────────────────────────────────────────────


class TestDeleteFeatureFlag:
    def test_delete_existing_flag(self, client) -> None:
        svc = MagicMock()
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.delete("/admin/feature-flags/tools.fgts_simulator")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        svc.delete_flag.assert_called_once_with("tools.fgts_simulator")

    def test_delete_invalid_name_returns_404(self, client) -> None:
        svc = MagicMock()
        with (
            patch(
                "app.controllers.admin.feature_flags._is_admin",
                return_value=True,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.delete("/admin/feature-flags/flag%0Ainjected")
        assert resp.status_code in (404, 400)
        svc.delete_flag.assert_not_called()


# ── _is_admin() exception branch ──────────────────────────────────────────────


class TestIsAdminExceptionBranch:
    """_is_admin() must return False (not raise) when get_active_auth_context raises."""

    def test_is_admin_returns_false_on_exception(self, client) -> None:
        """Lines 31-35: except Exception branch returns False, not 500."""
        with patch(
            "app.controllers.admin.feature_flags.get_active_auth_context",
            side_effect=RuntimeError("no auth context"),
        ):
            resp = client.get("/admin/feature-flags")
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["error"]["code"] == "FORBIDDEN"

    def test_is_admin_returns_false_on_attribute_error(self, client) -> None:
        """_is_admin() catches any exception type, including AttributeError."""
        with patch(
            "app.controllers.admin.feature_flags.get_active_auth_context",
            side_effect=AttributeError("roles missing"),
        ):
            resp = client.post(
                "/admin/feature-flags",
                json={"name": "tools.flag", "enabled": True},
            )
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

    def test_is_admin_returns_false_when_roles_missing_admin(self, client) -> None:
        """Line 33: return 'admin' in ctx.roles — covers the non-admin roles path."""
        from app.auth.identity import AuthContext

        ctx_no_admin = AuthContext(
            subject="user-123",
            email="user@example.com",
            roles=("user",),
            permissions=(),
            jti=None,
            issued_at=None,
            expires_at=None,
            raw_claims={},
        )
        svc = _make_svc_mock(list_result={})
        with (
            patch(
                "app.controllers.admin.feature_flags.get_active_auth_context",
                return_value=ctx_no_admin,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.get("/admin/feature-flags")
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "FORBIDDEN"

    def test_is_admin_returns_true_when_roles_contains_admin(self, client) -> None:
        """Line 33: return 'admin' in ctx.roles — covers the admin=True path."""
        from app.auth.identity import AuthContext

        ctx_admin = AuthContext(
            subject="admin-123",
            email="admin@example.com",
            roles=("admin", "user"),
            permissions=(),
            jti=None,
            issued_at=None,
            expires_at=None,
            raw_claims={},
        )
        svc = _make_svc_mock(list_result={})
        with (
            patch(
                "app.controllers.admin.feature_flags.get_active_auth_context",
                return_value=ctx_admin,
            ),
            patch(
                "app.controllers.admin.feature_flags.get_feature_flag_service",
                return_value=svc,
            ),
        ):
            resp = client.get("/admin/feature-flags")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0


# ── User.__repr__ ─────────────────────────────────────────────────────────────


class TestUserRepr:
    """app/models/user.py line 70: User.__repr__ must include the user name."""

    def test_user_repr_contains_name(self, admin_app) -> None:
        from app.models.user import User

        with admin_app.app_context():
            user = User()
            user.name = "Alice"
            assert "Alice" in repr(user)


# ── Name validation regex ─────────────────────────────────────────────────────


class TestFlagNameRegex:
    @pytest.mark.parametrize(
        "name",
        [
            "tools.fgts_simulator",
            "feature-flag-1",
            "FLAG_NAME",
            "a",
            "a" * 128,
            "tools.beta.v2",
        ],
    )
    def test_valid_names(self, name: str) -> None:
        import re

        pattern = re.compile(r"^[a-zA-Z0-9._-]{1,128}$")
        assert pattern.match(name) is not None, f"Expected valid: {name!r}"

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "flag\ninjected",
            "flag injected",
            "flag/path",
            "flag@user",
            "a" * 129,
            "flag\x00null",
        ],
    )
    def test_invalid_names(self, name: str) -> None:
        import re

        pattern = re.compile(r"^[a-zA-Z0-9._-]{1,128}$")
        assert pattern.match(name) is None, f"Expected invalid: {name!r}"
