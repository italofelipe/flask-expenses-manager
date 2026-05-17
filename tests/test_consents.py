"""Tests for the LGPD versioned consents endpoints (#1259).

Coverage targets:

- GET /me/consents returns latest event per kind
- POST /me/consents records a granted/revoked event (idempotent)
- DELETE /me/consents/<kind> records a REVOKED event (204)
- Auth required on all endpoints
- Cross-user isolation
- Marshmallow validation rejects unknown kind/action/source
- Consent model is registered in the LGPD registry
"""

from __future__ import annotations

import uuid

import pytest
from flask.testing import FlaskClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client: FlaskClient, prefix: str = "consent") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    password = "StrongPass@123"
    r = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201, r.get_json()
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200, r2.get_json()
    return r2.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _accept_body(
    *,
    kind: str = "terms",
    version: str = "1.0",
    action: str = "granted",
    source: str = "web",
) -> dict[str, str]:
    return {"kind": kind, "version": version, "action": action, "source": source}


# ---------------------------------------------------------------------------
# GET /me/consents
# ---------------------------------------------------------------------------


class TestListConsents:
    def test_empty_list_for_new_user(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.get("/me/consents", headers=_auth(token))
        assert res.status_code == 200
        body = res.get_json()
        assert body["data"]["total"] == 0
        assert body["data"]["items"] == []

    def test_list_returns_latest_event_per_kind(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        # Same kind, two versions — list should show the latest only.
        client.post(
            "/me/consents",
            json=_accept_body(kind="terms", version="1.0"),
            headers=_auth(token),
        )
        client.post(
            "/me/consents",
            json=_accept_body(kind="terms", version="2.0"),
            headers=_auth(token),
        )
        # Different kind — should show too.
        client.post(
            "/me/consents",
            json=_accept_body(kind="privacy", version="1.0"),
            headers=_auth(token),
        )
        res = client.get("/me/consents", headers=_auth(token))
        assert res.status_code == 200
        items = res.get_json()["data"]["items"]
        assert {i["kind"] for i in items} == {"terms", "privacy"}
        terms_entry = next(i for i in items if i["kind"] == "terms")
        assert terms_entry["version"] == "2.0"

    def test_list_requires_auth(self, client: FlaskClient) -> None:
        res = client.get("/me/consents")
        assert res.status_code in {401, 422}


# ---------------------------------------------------------------------------
# POST /me/consents
# ---------------------------------------------------------------------------


class TestRecordConsent:
    def test_grant_returns_201(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/me/consents",
            json=_accept_body(),
            headers=_auth(token),
        )
        assert res.status_code == 201, res.get_json()
        body = res.get_json()
        assert body["data"]["action"] == "granted"
        assert body["data"]["kind"] == "terms"
        assert body["data"]["version"] == "1.0"
        assert body["data"]["source"] == "web"
        assert "id" in body["data"]

    def test_idempotent_on_same_version_action(self, client: FlaskClient) -> None:
        """Replaying the same grant returns the original row's id."""
        token = _register_and_login(client)
        first = client.post(
            "/me/consents",
            json=_accept_body(),
            headers=_auth(token),
        )
        first_id = first.get_json()["data"]["id"]
        second = client.post(
            "/me/consents",
            json=_accept_body(),
            headers=_auth(token),
        )
        second_id = second.get_json()["data"]["id"]
        assert first_id == second_id

    def test_revoke_overrides_grant(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        client.post(
            "/me/consents",
            json=_accept_body(kind="ai", action="granted"),
            headers=_auth(token),
        )
        client.post(
            "/me/consents",
            json=_accept_body(kind="ai", action="revoked"),
            headers=_auth(token),
        )
        listing = client.get("/me/consents", headers=_auth(token))
        items = listing.get_json()["data"]["items"]
        ai_entry = next(i for i in items if i["kind"] == "ai")
        assert ai_entry["action"] == "revoked"

    def test_invalid_kind_returns_400(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/me/consents",
            json=_accept_body(kind="unknown_kind"),
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}

    def test_invalid_action_returns_400(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/me/consents",
            json=_accept_body(action="maybe"),
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}

    def test_invalid_source_returns_400(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/me/consents",
            json=_accept_body(source="telegram"),
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}

    def test_post_requires_auth(self, client: FlaskClient) -> None:
        res = client.post("/me/consents", json=_accept_body())
        assert res.status_code in {401, 422}


# ---------------------------------------------------------------------------
# DELETE /me/consents/<kind>
# ---------------------------------------------------------------------------


class TestRevokeShortcut:
    def test_delete_creates_revoke_event_returns_204(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        client.post(
            "/me/consents",
            json=_accept_body(kind="marketing"),
            headers=_auth(token),
        )
        res = client.delete("/me/consents/marketing", headers=_auth(token))
        assert res.status_code == 204
        listing = client.get("/me/consents", headers=_auth(token))
        items = listing.get_json()["data"]["items"]
        marketing = next(i for i in items if i["kind"] == "marketing")
        assert marketing["action"] == "revoked"
        # version is preserved from the previously accepted row.
        assert marketing["version"] == "1.0"

    def test_delete_without_prior_event_uses_default_version(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client)
        res = client.delete("/me/consents/cookies", headers=_auth(token))
        assert res.status_code == 204
        listing = client.get("/me/consents", headers=_auth(token))
        items = listing.get_json()["data"]["items"]
        cookies = next(i for i in items if i["kind"] == "cookies")
        assert cookies["action"] == "revoked"
        assert cookies["version"] == "1.0"

    def test_delete_invalid_kind_returns_400(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.delete("/me/consents/unknown", headers=_auth(token))
        assert res.status_code == 400
        body = res.get_json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_delete_requires_auth(self, client: FlaskClient) -> None:
        res = client.delete("/me/consents/terms")
        assert res.status_code in {401, 422}


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


class TestUserIsolation:
    def test_user_a_cannot_see_user_b_consents(self, client: FlaskClient) -> None:
        token_a = _register_and_login(client, "consent-a")
        token_b = _register_and_login(client, "consent-b")
        client.post(
            "/me/consents",
            json=_accept_body(kind="ai"),
            headers=_auth(token_a),
        )
        # User B's list must be empty — no leakage from user A.
        res = client.get("/me/consents", headers=_auth(token_b))
        assert res.status_code == 200
        assert res.get_json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# Registry hookup
# ---------------------------------------------------------------------------


def test_consent_model_is_in_lgpd_registry() -> None:
    """The Consent model must be registered for LGPD coverage."""
    from app.lgpd import REGISTRY
    from app.models.consent import Consent

    models = [r.model for r in REGISTRY]
    assert Consent in models
    consent_entry = next(r for r in REGISTRY if r.model is Consent)
    assert consent_entry.table_name == "consents"
    assert consent_entry.user_id_field == "user_id"
    assert consent_entry.export_included is True


# ---------------------------------------------------------------------------
# Service-level: record_consent idempotency direct test
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("app")
class TestServiceIdempotency:
    def test_record_consent_idempotent_returns_same_row(
        self, client: FlaskClient
    ) -> None:
        """Direct service call exercising the same idempotency contract."""
        from app.application.services.consent_service import record_consent
        from app.models.consent import ConsentAction, ConsentKind, ConsentSource

        token = _register_and_login(client, "svc-idem")
        # Resolve the user_id from /user/me
        me = client.get("/user/me", headers=_auth(token))
        # Endpoint may shape data differently — accept either top-level id
        # or nested under data.
        body = me.get_json()
        if "data" in body and isinstance(body["data"], dict) and "id" in body["data"]:
            user_id_str = body["data"]["id"]
        else:
            user_id_str = body.get("id") or body["data"]["user"]["id"]
        user_id = uuid.UUID(user_id_str)

        first = record_consent(
            user_id=user_id,
            kind=ConsentKind.TERMS,
            version="9.9",
            action=ConsentAction.GRANTED,
            source=ConsentSource.API,
        )
        second = record_consent(
            user_id=user_id,
            kind=ConsentKind.TERMS,
            version="9.9",
            action=ConsentAction.GRANTED,
            source=ConsentSource.WEB,  # different source, still idempotent
        )
        assert first.id == second.id
