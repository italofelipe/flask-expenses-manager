from __future__ import annotations

import uuid

from flask.testing import FlaskClient


def _register_and_login(
    client: FlaskClient,
    suffix: str | None = None,
) -> str:
    token_suffix = suffix or uuid.uuid4().hex[:8]
    email = f"alerts-{token_suffix}@test.com"
    password = "StrongPass@123"
    register = client.post(
        "/auth/register",
        json={
            "name": f"alerts-{token_suffix}",
            "email": email,
            "password": password,
        },
    )
    assert register.status_code == 201, register.get_json()
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.get_json()
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_alert_preferences_list_v2_contract(client: FlaskClient) -> None:
    token = _register_and_login(client, "prefs-v2")

    response = client.get(
        "/alerts/preferences",
        headers={**_auth(token), "X-API-Contract": "v2"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Preferências de alerta listadas com sucesso"
    assert body["data"]["preferences"] == []


def test_alert_preferences_reject_invalid_enabled_type(client: FlaskClient) -> None:
    token = _register_and_login(client, "prefs-invalid-enabled")

    response = client.put(
        "/alerts/preferences/wallet",
        json={"enabled": "true"},
        headers={**_auth(token), "X-API-Contract": "v2"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {"enabled": ["must_be_boolean"]}


def test_alert_preferences_reject_invalid_channels_type(client: FlaskClient) -> None:
    token = _register_and_login(client, "prefs-invalid-channels")

    response = client.put(
        "/alerts/preferences/wallet",
        json={"channels": ["email", 1]},
        headers={**_auth(token), "X-API-Contract": "v2"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {"channels": ["must_be_string_list"]}
