import uuid
from datetime import UTC, date, datetime, timedelta


def _register_and_login(client, prefix: str) -> str:
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


def _auth_headers(token: str, contract: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract:
        headers["X-API-Contract"] = contract
    return headers


def _transaction_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "title": "Conta de água",
        "amount": "120.50",
        "type": "expense",
        "due_date": date.today().isoformat(),
    }
    payload.update(overrides)
    return payload


def test_transaction_installment_create_success(client) -> None:
    token = _register_and_login(client, "installment")
    response = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json={
            **_transaction_payload(),
            "amount": "300.00",
            "is_installment": True,
            "installment_count": 3,
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    transactions = body["data"]["transactions"]
    assert len(transactions) == 3
    assert transactions[0]["title"].endswith("(1/3)")
    assert transactions[1]["title"].endswith("(2/3)")
    assert transactions[2]["title"].endswith("(3/3)")


def test_transaction_update_requires_paid_at_when_paid(client) -> None:
    token = _register_and_login(client, "paid-at-required")
    created = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json=_transaction_payload(),
    )
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    response = client.put(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(token, "v2"),
        json={"status": "paid"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_update_paid_at_without_paid_status(client) -> None:
    token = _register_and_login(client, "paid-at-status")
    created = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json=_transaction_payload(),
    )
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    response = client.put(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(token, "v2"),
        json={"status": "pending", "paid_at": datetime.now(UTC).isoformat()},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_update_paid_at_future_returns_400(client) -> None:
    token = _register_and_login(client, "paid-at-future")
    created = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json=_transaction_payload(),
    )
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]
    future_paid_at = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    response = client.put(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(token, "v2"),
        json={"status": "paid", "paid_at": future_paid_at},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_update_not_found_v2(client) -> None:
    token = _register_and_login(client, "update-not-found")
    missing_id = uuid.uuid4()

    response = client.put(
        f"/transactions/{missing_id}",
        headers=_auth_headers(token, "v2"),
        json={"title": "novo"},
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_transaction_update_forbidden_v2(client) -> None:
    owner_token = _register_and_login(client, "owner")
    other_token = _register_and_login(client, "other")

    created = client.post(
        "/transactions",
        headers=_auth_headers(owner_token, "v2"),
        json=_transaction_payload(),
    )
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    response = client.put(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(other_token, "v2"),
        json={"title": "hack"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_transaction_delete_not_found_v2(client) -> None:
    token = _register_and_login(client, "delete-not-found")
    missing_id = uuid.uuid4()

    response = client.delete(
        f"/transactions/{missing_id}",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_transaction_delete_forbidden_v2(client) -> None:
    owner_token = _register_and_login(client, "delete-owner")
    other_token = _register_and_login(client, "delete-other")

    created = client.post(
        "/transactions",
        headers=_auth_headers(owner_token, "v2"),
        json=_transaction_payload(),
    )
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    response = client.delete(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(other_token, "v2"),
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_transaction_deleted_list_v2(client) -> None:
    token = _register_and_login(client, "deleted-list")
    created = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json=_transaction_payload(),
    )
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    deleted = client.delete(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(token, "v2"),
    )
    assert deleted.status_code == 200

    response = client.get(
        "/transactions/deleted",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "deleted_transactions" in body["data"]
    assert len(body["data"]["deleted_transactions"]) >= 1


def test_transaction_summary_invalid_format_v2(client) -> None:
    token = _register_and_login(client, "summary-invalid")
    response = client.get(
        "/transactions/summary?month=invalid-format",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_create_recurring_requires_date_range(client) -> None:
    token = _register_and_login(client, "recurring-required-dates")
    response = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json={
            **_transaction_payload(),
            "is_recurring": True,
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_create_recurring_due_date_must_be_inside_range(client) -> None:
    token = _register_and_login(client, "recurring-range")
    response = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json={
            **_transaction_payload(due_date=date.today().isoformat()),
            "is_recurring": True,
            "start_date": (date.today() + timedelta(days=5)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_update_recurring_invalid_date_range(client) -> None:
    token = _register_and_login(client, "recurring-update-range")
    created = client.post(
        "/transactions",
        headers=_auth_headers(token, "v2"),
        json={
            **_transaction_payload(),
            "is_recurring": True,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
        },
    )
    assert created.status_code == 201
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    response = client.put(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(token, "v2"),
        json={
            "start_date": (date.today() + timedelta(days=40)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
