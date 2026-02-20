from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import requests

from app.extensions.integration_metrics import build_brapi_metrics_payload
from app.services.investment_service import InvestmentService


def _auth_headers(token: str, contract: str = "v2") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Contract": contract,
    }


def _register_and_login_rest(client: Any, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
        headers={"X-API-Contract": "v2"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"X-API-Contract": "v2"},
    )
    assert login_response.status_code == 200
    return str(login_response.get_json()["data"]["token"])


def _graphql(
    client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    token: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload: dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    return client.post("/graphql", json=payload, headers=headers)


def _register_and_login_graphql(client: Any, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    credentials = {
        "name": f"{prefix}-{suffix}",
        "email": f"{prefix}-{suffix}@email.com",
        "password": "StrongPass@123",
    }
    register_mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) {
        message
      }
    }
    """
    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    register_response = _graphql(client, register_mutation, credentials)
    assert register_response.status_code == 200
    login_response = _graphql(
        client,
        login_mutation,
        {"email": credentials["email"], "password": credentials["password"]},
    )
    assert login_response.status_code == 200
    return str(login_response.get_json()["data"]["login"]["token"])


def _force_brapi_timeout(monkeypatch: Any) -> None:
    monkeypatch.setenv("BRAPI_MAX_RETRIES", "0")
    InvestmentService._clear_cache_for_tests()

    def _raise_timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise requests.exceptions.Timeout("provider timeout")

    monkeypatch.setattr(requests, "get", _raise_timeout)


def test_rest_wallet_valuation_fallbacks_when_brapi_times_out(
    client: Any, monkeypatch: Any
) -> None:
    _force_brapi_timeout(monkeypatch)
    token = _register_and_login_rest(client, "rest-brapi-timeout")

    create_wallet = client.post(
        "/wallet",
        json={
            "name": "PETR4",
            "ticker": "PETR4",
            "quantity": 2,
            "register_date": "2026-02-09",
            "should_be_on_wallet": True,
        },
        headers=_auth_headers(token),
    )
    assert create_wallet.status_code == 201
    investment_id = str(create_wallet.get_json()["data"]["investment"]["id"])

    add_operation = client.post(
        f"/wallet/{investment_id}/operations",
        json={
            "operation_type": "buy",
            "quantity": "2",
            "unit_price": "10",
            "fees": "0",
            "executed_at": "2026-02-09",
        },
        headers=_auth_headers(token),
    )
    assert add_operation.status_code == 201

    valuation_response = client.get(
        f"/wallet/{investment_id}/valuation",
        headers=_auth_headers(token),
    )
    assert valuation_response.status_code == 200
    valuation = valuation_response.get_json()["data"]["valuation"]
    assert valuation["valuation_source"] == "fallback_cost_basis"
    assert valuation["market_price"] is None
    assert Decimal(valuation["invested_amount"]) == Decimal("20")
    assert Decimal(valuation["current_value"]) == Decimal("20")

    metrics = build_brapi_metrics_payload()
    assert metrics["summary"]["timeouts"] >= 1
    assert metrics["summary"]["invalid_payloads"] >= 1


def test_graphql_investment_valuation_fallbacks_when_brapi_times_out(
    client: Any, monkeypatch: Any
) -> None:
    _force_brapi_timeout(monkeypatch)
    token = _register_and_login_graphql(client, "graphql-brapi-timeout")

    add_wallet_mutation = """
    mutation AddWallet($registerDate: String!) {
      addWalletEntry(
        name: "PETR4",
        ticker: "PETR4",
        quantity: 2,
        registerDate: $registerDate,
        shouldBeOnWallet: true
      ) {
        item { id }
      }
    }
    """
    add_wallet_response = _graphql(
        client,
        add_wallet_mutation,
        {"registerDate": "2026-02-09"},
        token=token,
    )
    assert add_wallet_response.status_code == 200
    add_wallet_body = add_wallet_response.get_json()
    assert "errors" not in add_wallet_body
    investment_id = str(add_wallet_body["data"]["addWalletEntry"]["item"]["id"])

    add_operation_mutation = """
    mutation AddOperation($investmentId: UUID!, $executedAt: String!) {
      addInvestmentOperation(
        investmentId: $investmentId,
        operationType: "buy",
        quantity: "2",
        unitPrice: "10",
        fees: "0",
        executedAt: $executedAt
      ) {
        item { id }
      }
    }
    """
    add_operation_response = _graphql(
        client,
        add_operation_mutation,
        {"investmentId": investment_id, "executedAt": "2026-02-09"},
        token=token,
    )
    assert add_operation_response.status_code == 200
    assert "errors" not in add_operation_response.get_json()

    valuation_query = """
    query Valuation($investmentId: UUID!) {
      investmentValuation(investmentId: $investmentId) {
        valuationSource
        marketPrice
        investedAmount
        currentValue
      }
    }
    """
    valuation_response = _graphql(
        client,
        valuation_query,
        {"investmentId": investment_id},
        token=token,
    )
    assert valuation_response.status_code == 200
    valuation_body = valuation_response.get_json()
    assert "errors" not in valuation_body
    valuation = valuation_body["data"]["investmentValuation"]
    assert valuation["valuationSource"] == "fallback_cost_basis"
    assert valuation["marketPrice"] is None
    assert Decimal(valuation["investedAmount"]) == Decimal("20")
    assert Decimal(valuation["currentValue"]) == Decimal("20")

    metrics = build_brapi_metrics_payload()
    assert metrics["summary"]["timeouts"] >= 1
    assert metrics["summary"]["invalid_payloads"] >= 1
