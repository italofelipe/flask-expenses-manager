from __future__ import annotations

import uuid
from typing import Any, Dict


def _register_and_login(client, *, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={
            "name": f"user-{suffix}",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200
    return login_response.get_json()["token"]


def _auth_headers(token: str, contract: str | None = None) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract:
        headers["X-API-Contract"] = contract
    return headers


def _goal_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "title": "Reserva de emergência",
        "description": "Cobrir seis meses de despesas fixas",
        "category": "reserva",
        "target_amount": "15000.00",
        "current_amount": "2500.00",
        "priority": 1,
        "target_date": "2027-12-31",
    }
    payload.update(overrides)
    return payload


def test_goal_create_v1_legacy_contract(client) -> None:
    token = _register_and_login(client, prefix="goal-v1")
    response = client.post(
        "/goals",
        json=_goal_payload(),
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert "success" not in body
    assert body["message"] == "Meta criada com sucesso"
    assert body["goal"]["title"] == "Reserva de emergência"


def test_goal_crud_v2_contract(client) -> None:
    token = _register_and_login(client, prefix="goal-v2")

    create_response = client.post(
        "/goals",
        json=_goal_payload(),
        headers=_auth_headers(token, "v2"),
    )
    assert create_response.status_code == 201
    create_body = create_response.get_json()
    assert create_body["success"] is True
    goal_id = create_body["data"]["goal"]["id"]

    list_response = client.get(
        "/goals?page=1&per_page=10&status=active",
        headers=_auth_headers(token, "v2"),
    )
    assert list_response.status_code == 200
    list_body = list_response.get_json()
    assert list_body["success"] is True
    assert list_body["meta"]["pagination"]["total"] >= 1
    assert any(item["id"] == goal_id for item in list_body["data"]["items"])

    get_response = client.get(
        f"/goals/{goal_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert get_response.status_code == 200
    get_body = get_response.get_json()
    assert get_body["success"] is True
    assert get_body["data"]["goal"]["id"] == goal_id

    update_response = client.put(
        f"/goals/{goal_id}",
        json={"current_amount": "5000.00", "status": "paused"},
        headers=_auth_headers(token, "v2"),
    )
    assert update_response.status_code == 200
    update_body = update_response.get_json()
    assert update_body["success"] is True
    assert update_body["data"]["goal"]["status"] == "paused"
    assert update_body["data"]["goal"]["current_amount"] == "5000.00"

    delete_response = client.delete(
        f"/goals/{goal_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert delete_response.status_code == 200
    delete_body = delete_response.get_json()
    assert delete_body["success"] is True

    missing_response = client.get(
        f"/goals/{goal_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert missing_response.status_code == 404


def test_goal_forbidden_for_non_owner(client) -> None:
    owner_token = _register_and_login(client, prefix="goal-owner")
    other_token = _register_and_login(client, prefix="goal-other")

    create_response = client.post(
        "/goals",
        json=_goal_payload(),
        headers=_auth_headers(owner_token, "v2"),
    )
    assert create_response.status_code == 201
    goal_id = create_response.get_json()["data"]["goal"]["id"]

    forbidden_get = client.get(
        f"/goals/{goal_id}",
        headers=_auth_headers(other_token, "v2"),
    )
    assert forbidden_get.status_code == 403
    forbidden_body = forbidden_get.get_json()
    assert forbidden_body["success"] is False
    assert forbidden_body["error"]["code"] == "FORBIDDEN"


def test_goal_list_invalid_status_returns_validation_error(client) -> None:
    token = _register_and_login(client, prefix="goal-filter")
    response = client.get(
        "/goals?status=invalid-status",
        headers=_auth_headers(token, "v2"),
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_goal_plan_and_simulation_v2_contract(client) -> None:
    token = _register_and_login(client, prefix="goal-plan")

    profile_update = client.put(
        "/user/profile",
        json={
            "monthly_income": "9000.00",
            "monthly_expenses": "5000.00",
            "monthly_investment": "1200.00",
        },
        headers=_auth_headers(token, "v2"),
    )
    assert profile_update.status_code == 200

    create_response = client.post(
        "/goals",
        json=_goal_payload(target_amount="36000.00", current_amount="6000.00"),
        headers=_auth_headers(token, "v2"),
    )
    assert create_response.status_code == 201
    goal_id = create_response.get_json()["data"]["goal"]["id"]

    plan_response = client.get(
        f"/goals/{goal_id}/plan",
        headers=_auth_headers(token, "v2"),
    )
    assert plan_response.status_code == 200
    plan_body = plan_response.get_json()
    assert plan_body["success"] is True
    assert plan_body["data"]["goal_plan"]["horizon"] in {
        "short_term",
        "medium_term",
        "long_term",
    }
    assert "recommended_monthly_contribution" in plan_body["data"]["goal_plan"]
    assert isinstance(plan_body["data"]["goal_plan"]["recommendations"], list)

    simulation_response = client.post(
        "/goals/simulate",
        json={
            "target_amount": "50000.00",
            "current_amount": "10000.00",
            "monthly_income": "12000.00",
            "monthly_expenses": "7000.00",
            "monthly_contribution": "2000.00",
            "target_date": "2028-12-31",
        },
        headers=_auth_headers(token, "v2"),
    )
    assert simulation_response.status_code == 200
    simulation_body = simulation_response.get_json()
    assert simulation_body["success"] is True
    assert "goal_plan" in simulation_body["data"]
    assert "estimated_completion_date" in simulation_body["data"]["goal_plan"]
