import uuid
from datetime import date
from typing import Any, Dict


def _register_and_login(client) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"transaction-{suffix}@email.com"
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


def _transaction_payload() -> Dict[str, Any]:
    return {
        "title": "Conta de luz",
        "amount": "150.50",
        "type": "expense",
        "due_date": date.today().isoformat(),
    }


def test_transaction_create_v1_legacy_contract(client) -> None:
    token = _register_and_login(client)

    response = client.post(
        "/transactions",
        json=_transaction_payload(),
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert "success" not in body
    assert body["message"] == "Transação criada com sucesso"
    assert "transaction" in body


def test_transaction_create_v2_contract(client) -> None:
    token = _register_and_login(client)

    response = client.post(
        "/transactions",
        json=_transaction_payload(),
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Transação criada com sucesso"
    assert "transaction" in body["data"]


def test_transaction_list_and_summary_v2_contract(client) -> None:
    token = _register_and_login(client)
    create_response = client.post(
        "/transactions",
        json=_transaction_payload(),
        headers=_auth_headers(token, "v2"),
    )
    assert create_response.status_code == 201

    list_response = client.get(
        "/transactions/list",
        headers=_auth_headers(token, "v2"),
    )
    assert list_response.status_code == 200
    list_body = list_response.get_json()
    assert list_body["success"] is True
    assert "transactions" in list_body["data"]
    assert "pagination" in list_body["meta"]

    month_ref = date.today().strftime("%Y-%m")
    summary_response = client.get(
        f"/transactions/summary?month={month_ref}",
        headers=_auth_headers(token, "v2"),
    )
    assert summary_response.status_code == 200
    summary_body = summary_response.get_json()
    assert summary_body["success"] is True
    assert "income_total" in summary_body["data"]
    assert "expense_total" in summary_body["data"]
    assert "pagination" in summary_body["meta"]


def test_transaction_summary_missing_month_v2_contract(client) -> None:
    token = _register_and_login(client)

    response = client.get(
        "/transactions/summary",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_delete_restore_force_v2_contract(client) -> None:
    token = _register_and_login(client)
    create_response = client.post(
        "/transactions",
        json=_transaction_payload(),
        headers=_auth_headers(token, "v2"),
    )
    assert create_response.status_code == 201
    transaction_id = create_response.get_json()["data"]["transaction"][0]["id"]

    delete_response = client.delete(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert delete_response.status_code == 200
    delete_body = delete_response.get_json()
    assert delete_body["success"] is True

    restore_response = client.patch(
        f"/transactions/restore/{transaction_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert restore_response.status_code == 200
    restore_body = restore_response.get_json()
    assert restore_body["success"] is True

    delete_again_response = client.delete(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert delete_again_response.status_code == 200

    force_response = client.delete(
        f"/transactions/{transaction_id}/force",
        headers=_auth_headers(token, "v2"),
    )
    assert force_response.status_code == 200
    force_body = force_response.get_json()
    assert force_body["success"] is True
