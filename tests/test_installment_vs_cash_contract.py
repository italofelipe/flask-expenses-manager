from __future__ import annotations

import uuid

from app.models.user import User
from app.services.entitlement_service import grant_entitlement


def _register_and_login(client, *, prefix: str) -> tuple[str, str]:
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
    return login.get_json()["token"], email


def _auth(token: str, *, v2: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if v2:
        headers["X-API-Contract"] = "v2"
    return headers


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "cash_price": "900.00",
        "installment_count": 3,
        "installment_total": "990.00",
        "first_payment_delay_days": 30,
        "opportunity_rate_type": "manual",
        "opportunity_rate_annual": "12.00",
        "inflation_rate_annual": "4.50",
        "fees_enabled": False,
        "fees_upfront": "0.00",
    }
    payload.update(overrides)
    return payload


def _grant_advanced_simulations(client, email: str) -> None:
    with client.application.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None
        grant_entitlement(user.id, "advanced_simulations", source="manual")
        from app.extensions.database import db

        db.session.commit()


def test_installment_vs_cash_calculate_is_public(client) -> None:
    response = client.post(
        "/simulations/installment-vs-cash/calculate",
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["tool_id"] == "installment_vs_cash"
    assert body["rule_version"] == "2026.1"
    assert body["result"]["recommended_option"] in {
        "cash",
        "installment",
        "equivalent",
    }


def test_installment_vs_cash_calculate_supports_v2_contract(client) -> None:
    response = client.post(
        "/simulations/installment-vs-cash/calculate",
        json=_payload(),
        headers={"X-API-Contract": "v2"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["tool_id"] == "installment_vs_cash"


def test_installment_vs_cash_save_requires_auth(client) -> None:
    response = client.post(
        "/simulations/installment-vs-cash",
        json=_payload(),
    )

    assert response.status_code == 401


def test_installment_vs_cash_save_persists_simulation(client) -> None:
    token, _email = _register_and_login(client, prefix="installment-save")
    response = client.post(
        "/simulations/installment-vs-cash",
        json=_payload(scenario_label="Geladeira"),
        headers=_auth(token),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["simulation"]["tool_id"] == "installment_vs_cash"
    assert body["simulation"]["saved"] is True
    assert body["simulation"]["inputs"]["scenario_label"] == "Geladeira"


def test_installment_vs_cash_save_alias_emits_deprecation_headers(client) -> None:
    token, _email = _register_and_login(client, prefix="installment-save-compat")
    response = client.post(
        "/simulations/installment-vs-cash/save",
        json=_payload(scenario_label="Compat"),
        headers=_auth(token, v2=True),
    )

    assert response.status_code == 201
    assert response.headers["Deprecation"] == "true"
    assert response.headers["X-Auraxis-Successor-Endpoint"] == (
        "/simulations/installment-vs-cash"
    )
    assert response.headers["X-Auraxis-Successor-Method"] == "POST"


def test_installment_vs_cash_goal_bridge_requires_entitlement(client) -> None:
    token, email = _register_and_login(client, prefix="installment-goal-noent")
    # Simulate a downgraded/free user by revoking the trial entitlement
    with client.application.app_context():
        from app.extensions.database import db
        from app.services.entitlement_service import revoke_entitlement

        user = User.query.filter_by(email=email).first()
        assert user is not None
        revoke_entitlement(user.id, "advanced_simulations")
        db.session.commit()
    save_response = client.post(
        "/simulations/installment-vs-cash",
        json=_payload(),
        headers=_auth(token),
    )
    simulation_id = save_response.get_json()["simulation"]["id"]

    response = client.post(
        f"/simulations/{simulation_id}/goal",
        json={"title": "Notebook novo", "selected_option": "cash"},
        headers=_auth(token),
    )

    assert response.status_code == 403


def test_installment_vs_cash_goal_bridge_creates_goal_and_links_simulation(
    client,
) -> None:
    token, email = _register_and_login(client, prefix="installment-goal")
    _grant_advanced_simulations(client, email)
    save_response = client.post(
        "/simulations/installment-vs-cash",
        json=_payload(),
        headers=_auth(token),
    )
    simulation_id = save_response.get_json()["simulation"]["id"]

    response = client.post(
        f"/simulations/{simulation_id}/goal",
        json={"title": "Notebook novo", "selected_option": "cash"},
        headers=_auth(token),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["goal"]["title"] == "Notebook novo"
    assert body["goal"]["target_amount"] == "900.00"
    assert body["simulation"]["goal_id"] is not None


def test_installment_vs_cash_planned_expense_bridge_creates_installments_and_fee(
    client,
) -> None:
    token, email = _register_and_login(client, prefix="installment-expense")
    _grant_advanced_simulations(client, email)
    save_response = client.post(
        "/simulations/installment-vs-cash",
        json=_payload(fees_enabled=True, fees_upfront="60.00"),
        headers=_auth(token),
    )
    simulation_id = save_response.get_json()["simulation"]["id"]

    response = client.post(
        f"/simulations/{simulation_id}/planned-expense",
        json={
            "title": "Notebook novo",
            "selected_option": "installment",
            "first_due_date": "2026-04-15",
        },
        headers=_auth(token),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert len(body["transactions"]) == 4
    assert any(item["is_installment"] is True for item in body["transactions"])
    assert any(
        item["title"] == "Notebook novo - custos iniciais"
        for item in body["transactions"]
    )
