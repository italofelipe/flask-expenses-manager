"""Integration tests for Goal PATCH endpoint (J7-1 — partial update)."""

from __future__ import annotations

import uuid
from typing import Any, Dict


def _register_and_login(client, *, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    reg = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def _auth(token: str, v2: bool = False) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if v2:
        headers["X-API-Contract"] = "v2"
    return headers


def _goal_payload(**overrides: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "title": "Meta para testar PATCH",
        "target_amount": "10000.00",
        "priority": 2,
    }
    payload.update(overrides)
    return payload


def test_goal_patch_updates_partial_fields(client) -> None:
    token = _register_and_login(client, prefix="goal-patch")
    create_resp = client.post(
        "/goals",
        json=_goal_payload(),
        headers=_auth(token, v2=True),
    )
    assert create_resp.status_code == 201
    goal_id = create_resp.get_json()["data"]["goal"]["id"]

    patch_resp = client.patch(
        f"/goals/{goal_id}",
        json={"status": "paused"},
        headers=_auth(token, v2=True),
    )
    assert patch_resp.status_code == 200
    body = patch_resp.get_json()
    assert body["success"] is True
    assert body["data"]["goal"]["status"] == "paused"
    # Title should remain unchanged
    assert body["data"]["goal"]["title"] == "Meta para testar PATCH"


def test_goal_patch_requires_auth(client) -> None:
    resp = client.patch(f"/goals/{uuid.uuid4()}", json={"status": "paused"})
    assert resp.status_code == 401


def test_goal_patch_not_found(client) -> None:
    token = _register_and_login(client, prefix="goal-patch-nf")
    resp = client.patch(
        f"/goals/{uuid.uuid4()}",
        json={"status": "paused"},
        headers=_auth(token, v2=True),
    )
    assert resp.status_code == 404


def test_goal_patch_forbidden_for_non_owner(client) -> None:
    owner_token = _register_and_login(client, prefix="goal-patch-owner")
    other_token = _register_and_login(client, prefix="goal-patch-other")

    create_resp = client.post(
        "/goals",
        json=_goal_payload(),
        headers=_auth(owner_token, v2=True),
    )
    goal_id = create_resp.get_json()["data"]["goal"]["id"]

    patch_resp = client.patch(
        f"/goals/{goal_id}",
        json={"status": "paused"},
        headers=_auth(other_token, v2=True),
    )
    assert patch_resp.status_code == 403
