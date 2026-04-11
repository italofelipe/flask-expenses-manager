"""Tests that /transactions/list returns Deprecation headers (#840)."""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient


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


def test_transactions_list_has_deprecation_header(client: FlaskClient) -> None:
    token = _register_and_login(client, "depr-list")
    res = client.get(
        "/transactions/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.headers.get("Deprecation") == "true"
    assert res.headers.get("Sunset") is not None
    assert res.headers.get("X-Auraxis-Successor-Endpoint") == "/transactions"


def test_transactions_dashboard_has_deprecation_header(client: FlaskClient) -> None:
    token = _register_and_login(client, "depr-dash")
    res = client.get(
        "/transactions/dashboard?month=2030-06",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.headers.get("Deprecation") == "true"
