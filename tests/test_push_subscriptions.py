"""Tests for POST /notifications/subscribe and /notifications/unsubscribe (#1127)."""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client: FlaskClient, prefix: str = "push") -> str:
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


def _expo_token() -> str:
    return f"ExponentPushToken[{uuid.uuid4().hex}]"


def _web_push_body(endpoint: str | None = None) -> dict:
    return {
        "transport": "web_push",
        "endpoint": endpoint or f"https://fcm.googleapis.com/send/{uuid.uuid4().hex}",
        "keys": {"p256dh": "fake_key_abc", "auth": "fake_auth_abc"},
        "device_label": "Chrome — Desktop",
    }


# ---------------------------------------------------------------------------
# POST /notifications/subscribe — Expo
# ---------------------------------------------------------------------------


class TestSubscribeExpo:
    def test_register_expo_token_returns_200(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/subscribe",
            json={
                "transport": "expo",
                "endpoint": _expo_token(),
                "device_label": "iPhone 15",
            },
            headers=_auth(token),
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert body["data"]["transport"] == "expo"

    def test_register_expo_idempotent_upsert(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        ep = _expo_token()
        client.post(
            "/notifications/subscribe",
            json={"transport": "expo", "endpoint": ep, "device_label": "iPhone"},
            headers=_auth(token),
        )
        res = client.post(
            "/notifications/subscribe",
            json={"transport": "expo", "endpoint": ep, "device_label": "iPhone 15 Pro"},
            headers=_auth(token),
        )
        assert res.status_code == 200
        assert res.get_json()["data"]["device_label"] == "iPhone 15 Pro"

    def test_expo_invalid_token_format_returns_400(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/subscribe",
            json={"transport": "expo", "endpoint": "not-a-valid-expo-token"},
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}

    def test_subscribe_requires_auth(self, client: FlaskClient) -> None:
        res = client.post(
            "/notifications/subscribe",
            json={"transport": "expo", "endpoint": _expo_token()},
        )
        assert res.status_code in {401, 422}


# ---------------------------------------------------------------------------
# POST /notifications/subscribe — Web Push
# ---------------------------------------------------------------------------


class TestSubscribeWebPush:
    def test_register_web_push_returns_200(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/subscribe",
            json=_web_push_body(),
            headers=_auth(token),
        )
        assert res.status_code == 200
        assert res.get_json()["data"]["transport"] == "web_push"

    def test_web_push_missing_keys_returns_422(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/subscribe",
            json={
                "transport": "web_push",
                "endpoint": "https://fcm.googleapis.com/send/abc",
            },
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}

    def test_web_push_missing_auth_key_returns_422(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/subscribe",
            json={
                "transport": "web_push",
                "endpoint": "https://fcm.googleapis.com/send/abc",
                "keys": {"p256dh": "key_only"},
            },
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}


# ---------------------------------------------------------------------------
# POST /notifications/subscribe — invalid transport
# ---------------------------------------------------------------------------


class TestSubscribeInvalidTransport:
    def test_invalid_transport_returns_422(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/subscribe",
            json={"transport": "sms", "endpoint": "whatever"},
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}

    def test_missing_transport_returns_422(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/subscribe",
            json={"endpoint": _expo_token()},
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}


# ---------------------------------------------------------------------------
# POST /notifications/unsubscribe
# ---------------------------------------------------------------------------


class TestUnsubscribe:
    def test_unsubscribe_existing_returns_200(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        ep = _expo_token()
        client.post(
            "/notifications/subscribe",
            json={"transport": "expo", "endpoint": ep},
            headers=_auth(token),
        )
        res = client.post(
            "/notifications/unsubscribe",
            json={"endpoint": ep},
            headers=_auth(token),
        )
        assert res.status_code == 200
        assert res.get_json()["success"] is True

    def test_unsubscribe_not_found_returns_404(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/unsubscribe",
            json={"endpoint": "ExponentPushToken[doesnotexist]"},
            headers=_auth(token),
        )
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "NOT_FOUND"

    def test_unsubscribe_requires_auth(self, client: FlaskClient) -> None:
        res = client.post(
            "/notifications/unsubscribe",
            json={"endpoint": _expo_token()},
        )
        assert res.status_code in {401, 422}

    def test_unsubscribe_missing_endpoint_returns_422(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/notifications/unsubscribe",
            json={},
            headers=_auth(token),
        )
        assert res.status_code in {400, 422}

    def test_unsubscribe_isolates_by_user(self, client: FlaskClient) -> None:
        token_a = _register_and_login(client, "push-a")
        token_b = _register_and_login(client, "push-b")
        ep = _expo_token()
        client.post(
            "/notifications/subscribe",
            json={"transport": "expo", "endpoint": ep},
            headers=_auth(token_a),
        )
        # User B cannot unsubscribe user A's token
        res = client.post(
            "/notifications/unsubscribe",
            json={"endpoint": ep},
            headers=_auth(token_b),
        )
        assert res.status_code == 404
