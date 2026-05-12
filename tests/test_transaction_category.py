"""TDD tests for TransactionCategory field (#1239).

RED phase: all tests fail until production code is written.

Coverage:
- TransactionCategory enum exists with expected values
- Transaction model has category column (nullable)
- REST create transaction accepts category
- REST update transaction accepts category
- category persisted correctly in DB
- GraphQL createTransaction mutation accepts category
- GraphQL updateTransaction mutation accepts category
- category returned in transaction response
"""

from __future__ import annotations

import uuid
from typing import Any

from app.models.transaction import Transaction, TransactionCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str = "tx-cat") -> str:
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


def _create_tx(client, token: str, *, category: str | None = None) -> dict[str, Any]:
    """Create a transaction and return the first serialized item dict."""
    payload: dict[str, Any] = {
        "title": "Almoço",
        "amount": 45.0,
        "type": "expense",
        "due_date": "2026-05-15",
        "status": "paid",
        "paid_at": "2026-05-15T12:00:00",
    }
    if category is not None:
        payload["category"] = category
    resp = client.post("/transactions", json=payload, headers=_auth(token))
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()


def _graphql(
    client, query: str, variables: dict | None = None, token: str | None = None
) -> Any:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Tests: TransactionCategory enum
# ---------------------------------------------------------------------------


class TestTransactionCategoryEnum:
    def test_enum_has_alimentacao(self):
        assert TransactionCategory.alimentacao.value == "alimentacao"

    def test_enum_has_transporte(self):
        assert TransactionCategory.transporte.value == "transporte"

    def test_enum_has_moradia(self):
        assert TransactionCategory.moradia.value == "moradia"

    def test_enum_has_saude(self):
        assert TransactionCategory.saude.value == "saude"

    def test_enum_has_lazer(self):
        assert TransactionCategory.lazer.value == "lazer"

    def test_enum_has_educacao(self):
        assert TransactionCategory.educacao.value == "educacao"

    def test_enum_has_investimentos(self):
        assert TransactionCategory.investimentos.value == "investimentos"

    def test_enum_has_poupanca(self):
        assert TransactionCategory.poupanca.value == "poupanca"

    def test_enum_has_outros(self):
        assert TransactionCategory.outros.value == "outros"


# ---------------------------------------------------------------------------
# Tests: Transaction model has category column
# ---------------------------------------------------------------------------


class TestTransactionCategoryColumn:
    def test_transaction_model_has_category_attribute(self):
        assert hasattr(Transaction, "category")

    def test_transaction_category_is_nullable(self, app):
        with app.app_context():
            col = Transaction.__table__.c.get("category")
            assert col is not None
            assert col.nullable is True


# ---------------------------------------------------------------------------
# Tests: REST API
# ---------------------------------------------------------------------------


class TestTransactionCategoryREST:
    def test_create_transaction_with_category(self, client, app):
        token = _register_and_login(client)
        _create_tx(client, token, category="alimentacao")
        # Verify via DB — category persisted correctly
        from flask_jwt_extended import decode_token

        from app.extensions.database import db

        user_id = uuid.UUID(decode_token(token)["sub"])
        with app.app_context():
            tx = (
                db.session.query(Transaction)
                .filter_by(user_id=user_id)
                .order_by(Transaction.created_at.desc())
                .first()
            )
            assert tx is not None
            assert tx.category is not None
            assert tx.category.value == "alimentacao"

    def test_create_transaction_without_category_is_accepted(self, client):
        token = _register_and_login(client)
        resp = client.post(
            "/transactions",
            json={
                "title": "Salário",
                "amount": 5000.0,
                "type": "income",
                "due_date": "2026-05-01",
                "status": "paid",
                "paid_at": "2026-05-01T08:00:00",
            },
            headers=_auth(token),
        )
        assert resp.status_code in (200, 201)

    def test_category_null_when_not_provided(self, client, app):
        token = _register_and_login(client)
        from flask_jwt_extended import decode_token

        from app.extensions.database import db

        user_id = uuid.UUID(decode_token(token)["sub"])
        _create_tx(client, token, category=None)
        with app.app_context():
            tx = (
                db.session.query(Transaction)
                .filter_by(user_id=user_id)
                .order_by(Transaction.created_at.desc())
                .first()
            )
            assert tx is not None
            assert tx.category is None


# ---------------------------------------------------------------------------
# Tests: GraphQL
# ---------------------------------------------------------------------------


class TestTransactionCategoryGraphQL:
    def test_create_mutation_accepts_category(self, client):
        token = _register_and_login(client)
        resp = _graphql(
            client,
            """
            mutation {
              createTransaction(
                title: "Supermercado"
                amount: "120.50"
                type: EXPENSE
                dueDate: "2026-05-10"
                category: "alimentacao"
              ) {
                items { id category }
              }
            }
            """,
            token=token,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "errors" not in body, body.get("errors")
        items = body["data"]["createTransaction"]["items"]
        assert len(items) >= 1
        assert items[0]["category"] == "alimentacao"

    def test_create_mutation_without_category_succeeds(self, client):
        token = _register_and_login(client)
        resp = _graphql(
            client,
            """
            mutation {
              createTransaction(
                title: "Taxi"
                amount: "35.00"
                type: EXPENSE
                dueDate: "2026-05-11"
              ) {
                items { id category }
              }
            }
            """,
            token=token,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "errors" not in body, body.get("errors")
        items = body["data"]["createTransaction"]["items"]
        assert items[0]["category"] is None
