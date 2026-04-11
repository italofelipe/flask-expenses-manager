"""Tests for notification preferences ��� REST (#836) and GraphQL."""

from __future__ import annotations

import uuid
from typing import Any, Dict

from flask.testing import FlaskClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client: FlaskClient, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    password = "StrongPass@123"
    r = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _graphql(
    client: FlaskClient,
    query: str,
    variables: Dict[str, Any] | None = None,
    token: str | None = None,
):
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# REST — GET /user/notification-preferences
# ---------------------------------------------------------------------------


class TestNotificationPreferencesRESTGet:
    def test_get_returns_empty_list_for_new_user(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-get")
        res = client.get("/user/notification-preferences", headers=_auth(token))
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert body["data"]["preferences"] == []

    def test_get_requires_auth(self, client: FlaskClient) -> None:
        res = client.get("/user/notification-preferences")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# REST — PATCH /user/notification-preferences
# ---------------------------------------------------------------------------


class TestNotificationPreferencesRESTPatch:
    def test_patch_creates_preference(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-patch")
        res = client.patch(
            "/user/notification-preferences",
            json={"preferences": [{"category": "due_soon", "enabled": True}]},
            headers=_auth(token),
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        prefs = body["data"]["preferences"]
        assert len(prefs) == 1
        assert prefs[0]["category"] == "due_soon"
        assert prefs[0]["enabled"] is True

    def test_patch_upserts_existing_preference(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-upsert")
        client.patch(
            "/user/notification-preferences",
            json={"preferences": [{"category": "due_soon", "enabled": True}]},
            headers=_auth(token),
        )
        res = client.patch(
            "/user/notification-preferences",
            json={"preferences": [{"category": "due_soon", "enabled": False}]},
            headers=_auth(token),
        )
        assert res.status_code == 200
        prefs = res.get_json()["data"]["preferences"]
        assert prefs[0]["enabled"] is False

    def test_patch_invalid_category_returns_400(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-invalid")
        res = client.patch(
            "/user/notification-preferences",
            json={"preferences": [{"category": "invalid_category", "enabled": True}]},
            headers=_auth(token),
        )
        assert res.status_code == 400
        body = res.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_patch_missing_preferences_field_returns_400(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client, "notif-missing")
        res = client.patch(
            "/user/notification-preferences",
            json={},
            headers=_auth(token),
        )
        assert res.status_code == 400

    def test_patch_requires_auth(self, client: FlaskClient) -> None:
        res = client.patch(
            "/user/notification-preferences",
            json={"preferences": [{"category": "due_soon", "enabled": True}]},
        )
        assert res.status_code == 401

    def test_patch_global_opt_out(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-optout")
        res = client.patch(
            "/user/notification-preferences",
            json={
                "preferences": [
                    {"category": "wallet", "enabled": False, "global_opt_out": True}
                ]
            },
            headers=_auth(token),
        )
        assert res.status_code == 200
        prefs = res.get_json()["data"]["preferences"]
        assert prefs[0]["global_opt_out"] is True


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------

_NOTIFICATION_PREFS_QUERY = """
{
  notificationPreferences {
    preferences {
      category
      enabled
      globalOptOut
    }
  }
}
"""

_UPDATE_NOTIFICATION_PREFS = """
mutation UpdatePrefs($preferences: [PreferenceInput!]!) {
  updateNotificationPreferences(preferences: $preferences) {
    message
    preferences {
      category
      enabled
      globalOptOut
    }
  }
}
"""


class TestNotificationPreferencesGraphQL:
    def test_query_returns_empty_for_new_user(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-gql-q")
        res = _graphql(client, _NOTIFICATION_PREFS_QUERY, token=token)
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        prefs = body["data"]["notificationPreferences"]["preferences"]
        assert prefs == []

    def test_mutation_creates_preference(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-gql-m")
        res = _graphql(
            client,
            _UPDATE_NOTIFICATION_PREFS,
            {
                "preferences": [
                    {"category": "due_soon", "enabled": True, "globalOptOut": False}
                ]
            },
            token=token,
        )
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        data = body["data"]["updateNotificationPreferences"]
        assert "Preferências" in data["message"]
        prefs = data["preferences"]
        assert len(prefs) == 1
        assert prefs[0]["category"] == "due_soon"
        assert prefs[0]["enabled"] is True

    def test_mutation_invalid_category_returns_error(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-gql-inv")
        res = _graphql(
            client,
            _UPDATE_NOTIFICATION_PREFS,
            {
                "preferences": [
                    {"category": "bad_category", "enabled": True, "globalOptOut": False}
                ]
            },
            token=token,
        )
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

    def test_mutation_requires_auth(self, client: FlaskClient) -> None:
        res = _graphql(
            client,
            _UPDATE_NOTIFICATION_PREFS,
            {
                "preferences": [
                    {"category": "due_soon", "enabled": True, "globalOptOut": False}
                ]
            },
        )
        assert res.status_code in {200, 401}
        if res.status_code == 200:
            body = res.get_json()
            assert "errors" in body

    def test_query_returns_preferences_after_upsert(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "notif-gql-roundtrip")
        _graphql(
            client,
            _UPDATE_NOTIFICATION_PREFS,
            {
                "preferences": [
                    {"category": "goals", "enabled": False, "globalOptOut": False}
                ]
            },
            token=token,
        )
        res = _graphql(client, _NOTIFICATION_PREFS_QUERY, token=token)
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        prefs = body["data"]["notificationPreferences"]["preferences"]
        assert any(p["category"] == "goals" and p["enabled"] is False for p in prefs)
