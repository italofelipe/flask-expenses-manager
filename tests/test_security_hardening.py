from __future__ import annotations

import uuid
from typing import Any


def _register_and_login(client: Any) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"security-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={"name": f"security-{suffix}", "email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return str(login_response.get_json()["token"])


def test_payload_too_large_returns_413(client: Any) -> None:
    oversized_name = "a" * (1024 * 1024 + 100)
    response = client.post(
        "/auth/register",
        json={
            "name": oversized_name,
            "email": "oversized@email.com",
            "password": "StrongPass@123",
        },
    )

    assert response.status_code == 413
    body = response.get_json()
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_cors_headers_are_added_for_allowed_origin(client: Any) -> None:
    response = client.get(
        "/docs/",
        headers={"Origin": "https://frontend.local"},
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://frontend.local"
    assert "Origin" in response.headers["Vary"]


def test_user_me_rejects_limit_above_max(client: Any) -> None:
    token = _register_and_login(client)
    response = client.get(
        "/user/me?limit=999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert "limit" in body["message"]


def test_wallet_history_rejects_non_positive_per_page(client: Any) -> None:
    token = _register_and_login(client)
    create_wallet = client.post(
        "/wallet",
        headers={"Authorization": f"Bearer {token}", "X-API-Contract": "v2"},
        json={
            "name": "Reserva",
            "value": "100.00",
            "quantity": 1,
            "register_date": "2026-02-11",
            "should_be_on_wallet": True,
        },
    )
    assert create_wallet.status_code == 201
    investment_id = create_wallet.get_json()["data"]["investment"]["id"]

    response = client.get(
        f"/wallet/{investment_id}/history?per_page=0",
        headers={"Authorization": f"Bearer {token}", "X-API-Contract": "v2"},
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
