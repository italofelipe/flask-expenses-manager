"""Shared test helpers to avoid code duplication across test modules.

Import these instead of defining local copies in each test file.
"""

from __future__ import annotations

import uuid


def register_and_login(client, prefix: str) -> str:
    """Register a new user and log in; returns the access token."""
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def register_and_login_with_refresh(client, prefix: str) -> tuple[str, str]:
    """Register a new user and log in; returns (access_token, refresh_token)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"
    client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    body = resp.get_json()
    token = body.get("token") or (body.get("data") or {}).get("token")
    refresh = body.get("refresh_token") or (body.get("data") or {}).get("refresh_token")
    return token, refresh


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
