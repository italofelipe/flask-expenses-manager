"""Integration tests for configurable recurrence cadence (#1384).

Covers the end-to-end create flow: REST + GraphQL accept ``recurrence_interval``
and ``recurrence_unit``, persist them, and materialise future occurrences up to
``end_date`` immediately on create (the fix for recurring transactions not
appearing in future months).
"""

from __future__ import annotations

import uuid
from typing import Any

from flask_jwt_extended import decode_token

from app.extensions.database import db
from app.models.transaction import RecurrenceUnit, Transaction


def _register_and_login(client, prefix: str = "tx-rec") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    client.post(
        "/auth/register",
        json={"name": prefix, "email": email, "password": "StrongPass@123"},
    )
    login = client.post(
        "/auth/login", json={"email": email, "password": "StrongPass@123"}
    )
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _graphql(client, query: str, token: str | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/graphql", json={"query": query}, headers=headers)


def test_rest_create_recurring_materialises_future_months(client, app) -> None:
    token = _register_and_login(client)
    resp = client.post(
        "/transactions",
        json={
            "title": "Aluguel",
            "amount": 1000.0,
            "type": "expense",
            "due_date": "2026-05-05",
            "is_recurring": True,
            "start_date": "2026-05-05",
            "end_date": "2026-08-05",
            "recurrence_interval": 1,
            "recurrence_unit": "month",
        },
        headers=_auth(token),
    )
    assert resp.status_code in (200, 201), resp.get_json()

    user_id = uuid.UUID(decode_token(token)["sub"])
    with app.app_context():
        rows = (
            db.session.query(Transaction)
            .filter_by(user_id=user_id, title="Aluguel", deleted=False)
            .order_by(Transaction.due_date.asc())
            .all()
        )
        due_dates = [row.due_date.isoformat() for row in rows]
        assert due_dates == ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"]
        assert all(row.recurrence_unit == RecurrenceUnit.month for row in rows)
        assert all(row.recurrence_interval == 1 for row in rows)


def test_rest_create_recurring_weekly_interval(client, app) -> None:
    token = _register_and_login(client)
    resp = client.post(
        "/transactions",
        json={
            "title": "Feira",
            "amount": 100.0,
            "type": "expense",
            "due_date": "2026-05-01",
            "is_recurring": True,
            "start_date": "2026-05-01",
            "end_date": "2026-05-29",
            "recurrence_interval": 1,
            "recurrence_unit": "week",
        },
        headers=_auth(token),
    )
    assert resp.status_code in (200, 201), resp.get_json()

    user_id = uuid.UUID(decode_token(token)["sub"])
    with app.app_context():
        rows = (
            db.session.query(Transaction)
            .filter_by(user_id=user_id, title="Feira", deleted=False)
            .order_by(Transaction.due_date.asc())
            .all()
        )
        due_dates = [row.due_date.isoformat() for row in rows]
        assert due_dates == [
            "2026-05-01",
            "2026-05-08",
            "2026-05-15",
            "2026-05-22",
            "2026-05-29",
        ]


def test_graphql_create_accepts_recurrence_cadence(client) -> None:
    token = _register_and_login(client)
    resp = _graphql(
        client,
        """
        mutation {
          createTransaction(
            title: "Internet"
            amount: "99.90"
            type: EXPENSE
            dueDate: "2026-05-10"
            isRecurring: true
            startDate: "2026-05-10"
            endDate: "2026-07-10"
            recurrenceInterval: 1
            recurrenceUnit: "month"
          ) {
            message
            items { title recurrenceUnit recurrenceInterval isRecurring }
          }
        }
        """,
        token=token,
    )
    body = resp.get_json()
    assert "errors" not in body, body
    items = body["data"]["createTransaction"]["items"]
    assert items
    first = items[0]
    assert first["recurrenceUnit"] == "month"
    assert first["recurrenceInterval"] == 1
    assert first["isRecurring"] is True
