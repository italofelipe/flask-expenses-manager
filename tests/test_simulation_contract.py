"""Integration tests for Simulation persistence endpoints (J7-1)."""

from __future__ import annotations

import uuid
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _sim_payload(**overrides: Any) -> Dict[str, Any]:
    """Canonical payload using a tool_id present in TOOLS_REGISTRY."""
    payload: Dict[str, Any] = {
        "tool_id": "salary-net-clt",
        "rule_version": "2026.04",
        "inputs": {"gross": 5000},
        "result": {"net": 4100},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# POST /simulations — save simulation
# ---------------------------------------------------------------------------


def test_simulation_save_returns_201(client) -> None:
    token = _register_and_login(client, prefix="sim-save")
    resp = client.post("/simulations", json=_sim_payload(), headers=_auth(token))
    assert resp.status_code == 201
    body = resp.get_json()
    assert "simulation" in body
    assert body["simulation"]["tool_id"] == "salary-net-clt"
    assert body["simulation"]["saved"] is True


def test_simulation_save_requires_auth(client) -> None:
    resp = client.post("/simulations", json=_sim_payload())
    assert resp.status_code == 401


def test_simulation_save_missing_fields_returns_400(client) -> None:
    token = _register_and_login(client, prefix="sim-bad")
    resp = client.post(
        "/simulations",
        json={"tool_id": "salary_net"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /simulations — list
# ---------------------------------------------------------------------------


def test_simulation_list_empty(client) -> None:
    token = _register_and_login(client, prefix="sim-list-empty")
    resp = client.get("/simulations", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["items"] == []


def test_simulation_list_requires_auth(client) -> None:
    resp = client.get("/simulations")
    assert resp.status_code == 401


def test_simulation_list_after_save(client) -> None:
    token = _register_and_login(client, prefix="sim-list")
    client.post("/simulations", json=_sim_payload(), headers=_auth(token))
    resp = client.get("/simulations?page=1&per_page=20", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["tool_id"] == "salary-net-clt"


# ---------------------------------------------------------------------------
# GET /simulations/<id> — get single
# ---------------------------------------------------------------------------


def test_simulation_get_single(client) -> None:
    token = _register_and_login(client, prefix="sim-get")
    save_resp = client.post("/simulations", json=_sim_payload(), headers=_auth(token))
    sim_id = save_resp.get_json()["simulation"]["id"]

    resp = client.get(f"/simulations/{sim_id}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["simulation"]["id"] == sim_id


def test_simulation_get_requires_auth(client) -> None:
    resp = client.get(f"/simulations/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_simulation_get_not_found(client) -> None:
    token = _register_and_login(client, prefix="sim-notfound")
    resp = client.get(f"/simulations/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /simulations/<id> — delete
# ---------------------------------------------------------------------------


def test_simulation_delete(client) -> None:
    token = _register_and_login(client, prefix="sim-del")
    save_resp = client.post("/simulations", json=_sim_payload(), headers=_auth(token))
    sim_id = save_resp.get_json()["simulation"]["id"]

    del_resp = client.delete(f"/simulations/{sim_id}", headers=_auth(token))
    assert del_resp.status_code == 200

    get_resp = client.get(f"/simulations/{sim_id}", headers=_auth(token))
    assert get_resp.status_code == 404


def test_simulation_delete_requires_auth(client) -> None:
    resp = client.delete(f"/simulations/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_simulation_delete_not_found(client) -> None:
    token = _register_and_login(client, prefix="sim-del-nf")
    resp = client.delete(f"/simulations/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Isolation — user cannot access another user's simulation
# ---------------------------------------------------------------------------


def test_simulation_isolated_between_users(client) -> None:
    token_a = _register_and_login(client, prefix="sim-owner")
    token_b = _register_and_login(client, prefix="sim-other")

    save_resp = client.post("/simulations", json=_sim_payload(), headers=_auth(token_a))
    sim_id = save_resp.get_json()["simulation"]["id"]

    resp = client.get(f"/simulations/{sim_id}", headers=_auth(token_b))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# V2 contract smoke test
# ---------------------------------------------------------------------------


def test_simulation_v2_contract(client) -> None:
    token = _register_and_login(client, prefix="sim-v2")
    save_resp = client.post(
        "/simulations", json=_sim_payload(), headers=_auth(token, v2=True)
    )
    assert save_resp.status_code == 201
    body = save_resp.get_json()
    assert body["success"] is True
    sim_id = body["data"]["simulation"]["id"]

    list_resp = client.get("/simulations", headers=_auth(token, v2=True))
    assert list_resp.status_code == 200
    list_body = list_resp.get_json()
    assert list_body["success"] is True
    assert any(s["id"] == sim_id for s in list_body["data"]["items"])
