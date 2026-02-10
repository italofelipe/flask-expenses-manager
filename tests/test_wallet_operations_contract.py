import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict

from app.services.investment_service import InvestmentService


def _register_and_login(client, prefix: str = "wallet-op") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.get_json()["token"]


def _auth_headers(token: str, contract: str | None = None) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract:
        headers["X-API-Contract"] = contract
    return headers


def _create_wallet(client, token: str) -> str:
    response = client.post(
        "/wallet",
        json={
            "name": "Carteira Operacoes",
            "value": "1000.00",
            "quantity": 1,
            "register_date": "2026-02-09",
            "should_be_on_wallet": True,
        },
        headers=_auth_headers(token, "v2"),
    )
    assert response.status_code == 201
    return response.get_json()["data"]["investment"]["id"]


def _operation_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "operation_type": "buy",
        "quantity": "2.5",
        "unit_price": "35.40",
        "fees": "1.20",
        "executed_at": "2026-02-08",
        "notes": "Compra inicial",
    }
    payload.update(overrides)
    return payload


def test_wallet_operation_create_v2_contract(client) -> None:
    token = _register_and_login(client)
    investment_id = _create_wallet(client, token)

    response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(),
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["operation"]["operation_type"] == "buy"
    assert body["data"]["operation"]["quantity"] == "2.500000"


def test_wallet_operation_create_legacy_contract(client) -> None:
    token = _register_and_login(client)
    investment_id = _create_wallet(client, token)

    response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(operation_type="sell"),
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert "success" not in body
    assert body["operation"]["operation_type"] == "sell"


def test_wallet_operation_create_validation_error_v2(client) -> None:
    token = _register_and_login(client)
    investment_id = _create_wallet(client, token)

    response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(operation_type="invalid"),
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_wallet_operation_list_v2_contract_has_meta(client) -> None:
    token = _register_and_login(client)
    investment_id = _create_wallet(client, token)
    create_response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(),
        headers=_auth_headers(token, "v2"),
    )
    assert create_response.status_code == 201

    response = client.get(
        f"/wallet/{investment_id}/operations?page=1&per_page=10",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert len(body["data"]["items"]) == 1
    assert body["meta"]["pagination"]["total"] == 1


def test_wallet_operation_forbidden_for_other_user(client) -> None:
    owner_token = _register_and_login(client, "owner-op")
    other_token = _register_and_login(client, "other-op")
    investment_id = _create_wallet(client, owner_token)

    response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(),
        headers=_auth_headers(other_token, "v2"),
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_wallet_operation_update_delete_and_summary_v2(client) -> None:
    token = _register_and_login(client, "owner-op2")
    investment_id = _create_wallet(client, token)
    created_response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(quantity="10", unit_price="20"),
        headers=_auth_headers(token, "v2"),
    )
    operation_id = created_response.get_json()["data"]["operation"]["id"]

    update_response = client.put(
        f"/wallet/{investment_id}/operations/{operation_id}",
        json={"notes": "Atualizada", "fees": "2.00"},
        headers=_auth_headers(token, "v2"),
    )
    assert update_response.status_code == 200
    assert update_response.get_json()["data"]["operation"]["notes"] == "Atualizada"

    summary_response = client.get(
        f"/wallet/{investment_id}/operations/summary",
        headers=_auth_headers(token, "v2"),
    )
    assert summary_response.status_code == 200
    summary = summary_response.get_json()["data"]["summary"]
    assert summary["total_operations"] == 1
    assert summary["buy_operations"] == 1
    assert summary["sell_operations"] == 0
    assert summary["net_quantity"] == "10.000000"

    position_response = client.get(
        f"/wallet/{investment_id}/operations/position",
        headers=_auth_headers(token, "v2"),
    )
    assert position_response.status_code == 200
    position = position_response.get_json()["data"]["position"]
    assert position["current_quantity"] == "10.000000"
    assert Decimal(position["average_cost"]) == Decimal("20.2")

    delete_response = client.delete(
        f"/wallet/{investment_id}/operations/{operation_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert delete_response.status_code == 200
    assert delete_response.get_json()["success"] is True


def test_wallet_operation_position_with_buy_and_sell_v2(client) -> None:
    token = _register_and_login(client, "owner-op3")
    investment_id = _create_wallet(client, token)

    buy_response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(quantity="10", unit_price="10", fees="1.00"),
        headers=_auth_headers(token, "v2"),
    )
    assert buy_response.status_code == 201

    sell_response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(operation_type="sell", quantity="4", unit_price="13"),
        headers=_auth_headers(token, "v2"),
    )
    assert sell_response.status_code == 201

    position_response = client.get(
        f"/wallet/{investment_id}/operations/position",
        headers=_auth_headers(token, "v2"),
    )
    assert position_response.status_code == 200
    position = position_response.get_json()["data"]["position"]
    assert position["buy_operations"] == 1
    assert position["sell_operations"] == 1
    assert position["total_buy_quantity"] == "10.000000"
    assert position["total_sell_quantity"] == "4.000000"
    assert position["current_quantity"] == "6.000000"
    assert Decimal(position["current_cost_basis"]) == Decimal("60.6")
    assert Decimal(position["average_cost"]) == Decimal("10.1")


def test_wallet_operation_invested_amount_by_date_v2(client) -> None:
    token = _register_and_login(client, "owner-op4")
    investment_id = _create_wallet(client, token)

    first_buy = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(quantity="10", unit_price="10", fees="1.00"),
        headers=_auth_headers(token, "v2"),
    )
    assert first_buy.status_code == 201

    first_sell = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(operation_type="sell", quantity="4", unit_price="13"),
        headers=_auth_headers(token, "v2"),
    )
    assert first_sell.status_code == 201

    response = client.get(
        f"/wallet/{investment_id}/operations/invested-amount?date=2026-02-08",
        headers=_auth_headers(token, "v2"),
    )
    assert response.status_code == 200
    result = response.get_json()["data"]["result"]
    assert result["date"] == "2026-02-08"
    assert result["total_operations"] == 2
    assert result["buy_operations"] == 1
    assert result["sell_operations"] == 1
    assert Decimal(result["buy_amount"]) == Decimal("101")
    assert Decimal(result["sell_amount"]) == Decimal("50.8")
    assert Decimal(result["net_invested_amount"]) == Decimal("50.2")


def test_wallet_portfolio_and_investment_valuation_v2(client, monkeypatch) -> None:
    token = _register_and_login(client, "owner-op5")
    InvestmentService._clear_cache_for_tests()
    monkeypatch.setattr(InvestmentService, "get_market_price", lambda _ticker: 25.0)

    ticker_wallet_response = client.post(
        "/wallet",
        json={
            "name": "PETR4",
            "ticker": "PETR4",
            "quantity": 2,
            "register_date": "2026-02-09",
            "should_be_on_wallet": True,
        },
        headers=_auth_headers(token, "v2"),
    )
    assert ticker_wallet_response.status_code == 201
    ticker_wallet_id = ticker_wallet_response.get_json()["data"]["investment"]["id"]

    fixed_wallet_response = client.post(
        "/wallet",
        json={
            "name": "Reserva",
            "value": "500.00",
            "register_date": "2026-02-09",
            "should_be_on_wallet": True,
        },
        headers=_auth_headers(token, "v2"),
    )
    assert fixed_wallet_response.status_code == 201

    investment_response = client.get(
        f"/wallet/{ticker_wallet_id}/valuation",
        headers=_auth_headers(token, "v2"),
    )
    assert investment_response.status_code == 200
    valuation = investment_response.get_json()["data"]["valuation"]
    assert valuation["valuation_source"] == "brapi_market_price"
    assert Decimal(valuation["invested_amount"]) == Decimal("50")
    assert Decimal(valuation["current_value"]) == Decimal("50")
    assert Decimal(valuation["profit_loss_amount"]) == Decimal("0")
    assert Decimal(valuation["profit_loss_percent"]) == Decimal("0")

    portfolio_response = client.get(
        "/wallet/valuation",
        headers=_auth_headers(token, "v2"),
    )
    assert portfolio_response.status_code == 200
    payload = portfolio_response.get_json()["data"]
    assert payload["summary"]["total_investments"] == 2
    assert payload["summary"]["with_market_data"] == 1
    assert Decimal(payload["summary"]["total_invested_amount"]) == Decimal("550")
    assert Decimal(payload["summary"]["total_current_value"]) == Decimal("550")
    assert Decimal(payload["summary"]["total_profit_loss"]) == Decimal("0")


def test_wallet_portfolio_valuation_history_v2(client) -> None:
    token = _register_and_login(client, "owner-op6")
    investment_id = _create_wallet(client, token)

    buy_response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(quantity="10", unit_price="10", fees="1.00"),
        headers=_auth_headers(token, "v2"),
    )
    assert buy_response.status_code == 201

    sell_response = client.post(
        f"/wallet/{investment_id}/operations",
        json=_operation_payload(operation_type="sell", quantity="4", unit_price="13"),
        headers=_auth_headers(token, "v2"),
    )
    assert sell_response.status_code == 201

    response = client.get(
        "/wallet/valuation/history?startDate=2026-02-08&finalDate=2026-02-09",
        headers=_auth_headers(token, "v2"),
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["summary"]["total_points"] == 2
    assert Decimal(body["data"]["summary"]["total_buy_amount"]) == Decimal("101")
    assert Decimal(body["data"]["summary"]["total_sell_amount"]) == Decimal("50.8")
    assert Decimal(body["data"]["summary"]["total_net_invested_amount"]) == Decimal(
        "50.2"
    )
    assert Decimal(body["data"]["summary"]["final_cumulative_net_invested"]) == Decimal(
        "50.2"
    )
    first_item = body["data"]["items"][0]
    assert first_item["date"] == "2026-02-08"
    assert first_item["total_operations"] == 2
    assert "total_current_value_estimate" in first_item
    assert "total_profit_loss_estimate" in first_item


def test_wallet_fixed_income_valuation_v2(client) -> None:
    token = _register_and_login(client, "owner-op7")
    register_date = (date.today() - timedelta(days=30)).isoformat()

    response = client.post(
        "/wallet",
        json={
            "name": "CDB Banco X",
            "value": "1000.00",
            "quantity": 1,
            "asset_class": "cdb",
            "annual_rate": "12.0",
            "register_date": register_date,
            "should_be_on_wallet": True,
        },
        headers=_auth_headers(token, "v2"),
    )
    assert response.status_code == 201
    investment_id = response.get_json()["data"]["investment"]["id"]

    valuation_response = client.get(
        f"/wallet/{investment_id}/valuation",
        headers=_auth_headers(token, "v2"),
    )
    assert valuation_response.status_code == 200
    valuation = valuation_response.get_json()["data"]["valuation"]
    assert valuation["asset_class"] == "cdb"
    assert valuation["valuation_source"] == "fixed_income_projection"
    assert Decimal(valuation["current_value"]) >= Decimal(valuation["invested_amount"])
