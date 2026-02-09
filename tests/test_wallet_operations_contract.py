import uuid
from typing import Any, Dict


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

    delete_response = client.delete(
        f"/wallet/{investment_id}/operations/{operation_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert delete_response.status_code == 200
    assert delete_response.get_json()["success"] is True
