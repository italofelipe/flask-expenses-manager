import uuid
from typing import Any, Dict


def _register_and_login(client) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"wallet-{suffix}@email.com"
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


def _wallet_payload() -> Dict[str, Any]:
    return {
        "name": "Reserva",
        "value": "1500.00",
        "quantity": 2,
        "register_date": "2026-02-08",
        "should_be_on_wallet": True,
    }


def test_wallet_create_v1_legacy_contract(client) -> None:
    token = _register_and_login(client)
    response = client.post(
        "/wallet",
        json=_wallet_payload(),
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert "success" not in body
    assert body["message"] == "Ativo cadastrado com sucesso"
    assert "investment" in body


def test_wallet_create_v2_contract(client) -> None:
    token = _register_and_login(client)
    response = client.post(
        "/wallet",
        json=_wallet_payload(),
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Ativo cadastrado com sucesso"
    assert "investment" in body["data"]


def test_wallet_validation_error_v2_contract(client) -> None:
    token = _register_and_login(client)
    response = client.post(
        "/wallet",
        json={
            "name": "Inválido sem value e sem ticker",
            "should_be_on_wallet": True,
        },
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "messages" in body["error"]["details"]


def test_wallet_list_v2_contract_has_meta_pagination(client) -> None:
    token = _register_and_login(client)
    create_response = client.post(
        "/wallet",
        json=_wallet_payload(),
        headers=_auth_headers(token, "v2"),
    )
    assert create_response.status_code == 201

    list_response = client.get(
        "/wallet?page=1&per_page=10", headers=_auth_headers(token, "v2")
    )

    assert list_response.status_code == 200
    body = list_response.get_json()
    assert body["success"] is True
    assert "items" in body["data"]
    assert "pagination" in body["meta"]
    assert body["meta"]["pagination"]["page"] == 1


def test_wallet_update_and_history_v2_contract(client) -> None:
    token = _register_and_login(client)
    create_response = client.post(
        "/wallet",
        json=_wallet_payload(),
        headers=_auth_headers(token, "v2"),
    )
    assert create_response.status_code == 201
    investment_id = create_response.get_json()["data"]["investment"]["id"]

    update_response = client.put(
        f"/wallet/{investment_id}",
        json={"value": "2000.00"},
        headers=_auth_headers(token, "v2"),
    )
    assert update_response.status_code == 200
    update_body = update_response.get_json()
    assert update_body["success"] is True
    assert update_body["data"]["investment"]["history"]

    history_response = client.get(
        f"/wallet/{investment_id}/history?page=1&per_page=10",
        headers=_auth_headers(token, "v2"),
    )
    assert history_response.status_code == 200
    history_body = history_response.get_json()
    assert history_body["success"] is True
    assert "items" in history_body["data"]
    assert "pagination" in history_body["meta"]
