from __future__ import annotations

import uuid
from datetime import date
from typing import Any


def _register_and_login(client, prefix: str = "tx-refactor") -> str:
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
    return str(login_response.get_json()["token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _transaction_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Conta refatoração",
        "amount": "150.00",
        "type": "expense",
        "due_date": date.today().isoformat(),
    }
    payload.update(overrides)
    return payload


def test_transaction_endpoints_return_401_when_token_is_revoked(
    client, monkeypatch
) -> None:
    token = _register_and_login(client, "revoked")
    created = client.post(
        "/transactions",
        headers=_auth_headers(token),
        json=_transaction_payload(),
    )
    assert created.status_code == 201
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    monkeypatch.setattr(
        "app.controllers.transaction_controller.is_token_revoked",
        lambda _jti: True,
    )

    scenarios = [
        ("POST", "/transactions", _transaction_payload()),
        ("PUT", f"/transactions/{transaction_id}", {"title": "novo título"}),
        ("DELETE", f"/transactions/{transaction_id}", None),
        ("PATCH", f"/transactions/restore/{transaction_id}", None),
        ("GET", "/transactions/deleted", None),
        ("GET", "/transactions/list", None),
        ("GET", f"/transactions/summary?month={date.today().strftime('%Y-%m')}", None),
        (
            "GET",
            f"/transactions/dashboard?month={date.today().strftime('%Y-%m')}",
            None,
        ),
        ("DELETE", f"/transactions/{transaction_id}/force", None),
        ("GET", f"/transactions/expenses?finalDate={date.today().isoformat()}", None),
    ]

    for method, url, body in scenarios:
        response = client.open(
            url,
            method=method,
            headers=_auth_headers(token),
            json=body,
        )
        assert response.status_code == 401
        payload = response.get_json()
        assert payload["success"] is False
        assert payload["error"]["code"] == "UNAUTHORIZED"


def test_transaction_installment_create_handles_internal_error(
    client, monkeypatch
) -> None:
    token = _register_and_login(client, "installment-error")
    monkeypatch.setattr(
        "app.controllers.transaction_controller._build_installment_amounts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = client.post(
        "/transactions",
        headers=_auth_headers(token),
        json=_transaction_payload(
            is_installment=True,
            installment_count=2,
            amount="300.00",
        ),
    )

    assert response.status_code == 500
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"


def test_transaction_list_rejects_invalid_type_and_page(client) -> None:
    token = _register_and_login(client, "invalid-list-filters")

    invalid_type = client.get(
        "/transactions/list?type=invalid",
        headers=_auth_headers(token),
    )
    assert invalid_type.status_code == 400
    assert invalid_type.get_json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_page = client.get(
        "/transactions/list?page=abc",
        headers=_auth_headers(token),
    )
    assert invalid_page.status_code == 400
    assert invalid_page.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_expenses_rejects_invalid_order_and_period(client) -> None:
    token = _register_and_login(client, "invalid-expense-order")

    invalid_period = client.get(
        "/transactions/expenses?startDate=2026-02-11&finalDate=2026-02-10",
        headers=_auth_headers(token),
    )
    assert invalid_period.status_code == 400
    assert invalid_period.get_json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_order = client.get(
        f"/transactions/expenses?finalDate={date.today().isoformat()}&order_by=invalid",
        headers=_auth_headers(token),
    )
    assert invalid_order.status_code == 400
    assert invalid_order.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_transaction_summary_and_dashboard_handle_analytics_failures(
    client, monkeypatch
) -> None:
    token = _register_and_login(client, "analytics-failure")

    class _BrokenAnalyticsService:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def get_month_transactions(self, **_kwargs: object) -> list[object]:
            return []

        def get_month_aggregates(self, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError("analytics unavailable")

    monkeypatch.setattr(
        "app.controllers.transaction_controller.TransactionAnalyticsService",
        _BrokenAnalyticsService,
    )

    summary_response = client.get(
        f"/transactions/summary?month={date.today().strftime('%Y-%m')}",
        headers=_auth_headers(token),
    )
    assert summary_response.status_code == 500
    assert summary_response.get_json()["error"]["code"] == "INTERNAL_ERROR"

    dashboard_response = client.get(
        f"/transactions/dashboard?month={date.today().strftime('%Y-%m')}",
        headers=_auth_headers(token),
    )
    assert dashboard_response.status_code == 500
    assert dashboard_response.get_json()["error"]["code"] == "INTERNAL_ERROR"
