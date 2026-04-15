"""Entitlement matrix enforcement tests (issue #1057).

Verifies that every premium-gated endpoint returns 403 ENTITLEMENT_REQUIRED
when accessed by a free user (all premium entitlements revoked).

The test matrix must stay in sync with:
- docs/entitlement-matrix.md
- scripts/entitlement_coverage_check.py DOCUMENTED_REST_GUARDS
"""

from __future__ import annotations

import uuid

import pytest

from app.config.plan_features import PREMIUM_FEATURES
from app.services.entitlement_service import revoke_entitlement

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, *, prefix: str) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@auraxis.test"
    password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.get_json()["token"]
    profile = client.get("/user/profile", headers={"Authorization": f"Bearer {token}"})
    body = profile.get_json()
    user_id = body.get("data", {}).get("id") or body["user"]["id"]
    return token, user_id


def _downgrade_to_free(app, user_id: str) -> None:
    """Revoke all premium entitlements to simulate a downgraded free user."""
    with app.app_context():
        from app.extensions.database import db

        for feature in PREMIUM_FEATURES:
            revoke_entitlement(uuid.UUID(user_id), feature)
        db.session.commit()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Matrix: (method, url, body) for each premium endpoint
# ---------------------------------------------------------------------------

_PREMIUM_ENDPOINTS: list[tuple[str, str, dict | None]] = [
    # GET /transactions/export — export_pdf entitlement
    ("GET", "/transactions/export", None),
    # POST /simulations/{id}/goal — advanced_simulations
    ("POST", f"/simulations/{uuid.uuid4()}/goal", {"period_months": 12}),
    # POST /simulations/{id}/planned-expense — advanced_simulations
    (
        "POST",
        f"/simulations/{uuid.uuid4()}/planned-expense",
        {"planned_month": "2026-06"},
    ),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFreeUserCannotAccessPremiumEndpoints:
    """Every premium endpoint must return 403 ENTITLEMENT_REQUIRED for free users."""

    @pytest.fixture(autouse=True)
    def _free_user(self, app, client):
        self.token, self.user_id = _register_and_login(client, prefix="entmat-free")
        _downgrade_to_free(app, self.user_id)

    @pytest.mark.parametrize("method,url,body", _PREMIUM_ENDPOINTS)
    def test_premium_endpoint_returns_403_for_free_user(
        self, client, method: str, url: str, body: dict | None
    ) -> None:
        headers = _auth(self.token)
        if method == "GET":
            resp = client.get(url, headers=headers)
        elif method == "POST":
            resp = client.post(url, json=body or {}, headers=headers)
        else:
            pytest.fail(f"Unexpected HTTP method: {method}")

        assert resp.status_code == 403, (
            f"{method} {url} returned {resp.status_code}, expected 403"
        )
        body_json = resp.get_json()
        assert body_json is not None
        # Both legacy {"error": "..."} and new {"error": {"code": "..."}} shapes
        error = body_json.get("error", {})
        if isinstance(error, dict):
            assert error.get("code") == "ENTITLEMENT_REQUIRED", (
                f"Expected ENTITLEMENT_REQUIRED, got: {body_json}"
            )
        else:
            # Legacy string error from require_entitlement
            assert "entitlement" in str(error).lower(), (
                f"Expected entitlement error message, got: {body_json}"
            )

    def test_unauthenticated_gets_401_not_403(self, client) -> None:
        """Unauthenticated requests must fail at auth, not entitlement."""
        resp = client.get("/transactions/export")
        assert resp.status_code == 401

    def test_premium_endpoints_count_matches_matrix(self) -> None:
        """Guard: if you add a REST endpoint to the matrix, add a test too."""
        from scripts.entitlement_coverage_check import DOCUMENTED_REST_GUARDS

        matrix_file_count = len({rel for rel, _ in DOCUMENTED_REST_GUARDS})
        # Each file in the matrix must produce at least one test case.
        # This assertion fails if DOCUMENTED_REST_GUARDS grows without updating
        # _PREMIUM_ENDPOINTS above.
        assert len(_PREMIUM_ENDPOINTS) >= matrix_file_count, (
            f"There are {matrix_file_count} files in DOCUMENTED_REST_GUARDS "
            f"but only {len(_PREMIUM_ENDPOINTS)} endpoint(s) in _PREMIUM_ENDPOINTS. "
            "Update _PREMIUM_ENDPOINTS in this file."
        )
