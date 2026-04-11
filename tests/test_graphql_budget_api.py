"""Integration tests for Budget GraphQL queries and mutations (#886)."""

from __future__ import annotations

import uuid
from typing import Any, Dict


def _graphql(
    client,
    query: str,
    variables: Dict[str, Any] | None = None,
    token: str | None = None,
):
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


def _register_and_login(client, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    password = "StrongPass@123"
    r = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.get_json()["token"]


_CREATE_BUDGET = """
mutation CreateBudget($name: String!, $amount: String!, $period: String!) {
  createBudget(name: $name, amount: $amount, period: $period) {
    message
    budget {
      id name amount period isActive spent remaining percentageUsed isOverBudget
    }
  }
}
"""

_UPDATE_BUDGET = """
mutation UpdateBudget($budgetId: UUID!, $name: String) {
  updateBudget(budgetId: $budgetId, name: $name) {
    message
    budget { id name }
  }
}
"""

_DELETE_BUDGET = """
mutation DeleteBudget($budgetId: UUID!) {
  deleteBudget(budgetId: $budgetId) {
    ok
    message
  }
}
"""

_LIST_BUDGETS = """
{
  budgets {
    items {
      id name amount period isActive spent remaining percentageUsed isOverBudget
    }
  }
}
"""

_BUDGET_SUMMARY = """
{
  budgetSummary {
    totalBudgeted totalSpent totalRemaining percentageUsed budgetCount
  }
}
"""

_GET_BUDGET = """
query GetBudget($budgetId: UUID!) {
  budget(budgetId: $budgetId) {
    id name amount period isActive spent remaining percentageUsed isOverBudget
  }
}
"""


class TestBudgetGraphQLCRUD:
    def test_create_budget_returns_budget(self, client) -> None:
        token = _register_and_login(client, "budget-gql")
        res = _graphql(
            client,
            _CREATE_BUDGET,
            {"name": "Alimentação", "amount": "500.00", "period": "monthly"},
            token=token,
        )
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        data = body["data"]["createBudget"]
        assert data["message"] == "Orçamento criado com sucesso"
        budget = data["budget"]
        assert budget["name"] == "Alimentação"
        assert budget["isActive"] is True
        assert budget["spent"] is not None

    def test_list_budgets_returns_items(self, client) -> None:
        token = _register_and_login(client, "budget-list")
        _graphql(
            client,
            _CREATE_BUDGET,
            {"name": "Transporte", "amount": "300.00", "period": "monthly"},
            token=token,
        )

        res = _graphql(client, _LIST_BUDGETS, token=token)
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        items = body["data"]["budgets"]["items"]
        assert len(items) >= 1
        assert any(b["name"] == "Transporte" for b in items)

    def test_get_budget_by_id(self, client) -> None:
        token = _register_and_login(client, "budget-getid")
        create_res = _graphql(
            client,
            _CREATE_BUDGET,
            {"name": "Lazer", "amount": "200.00", "period": "monthly"},
            token=token,
        )
        budget_id = create_res.get_json()["data"]["createBudget"]["budget"]["id"]

        res = _graphql(client, _GET_BUDGET, {"budgetId": budget_id}, token=token)
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        assert body["data"]["budget"]["id"] == budget_id
        assert body["data"]["budget"]["name"] == "Lazer"

    def test_get_budget_not_found_returns_error(self, client) -> None:
        token = _register_and_login(client, "budget-notfound")
        res = _graphql(
            client, _GET_BUDGET, {"budgetId": str(uuid.uuid4())}, token=token
        )
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "NOT_FOUND"

    def test_update_budget_changes_name(self, client) -> None:
        token = _register_and_login(client, "budget-upd")
        create_res = _graphql(
            client,
            _CREATE_BUDGET,
            {"name": "Original", "amount": "100.00", "period": "monthly"},
            token=token,
        )
        budget_id = create_res.get_json()["data"]["createBudget"]["budget"]["id"]

        res = _graphql(
            client,
            _UPDATE_BUDGET,
            {"budgetId": budget_id, "name": "Atualizado"},
            token=token,
        )
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        assert body["data"]["updateBudget"]["budget"]["name"] == "Atualizado"

    def test_delete_budget_removes_it(self, client) -> None:
        token = _register_and_login(client, "budget-del")
        create_res = _graphql(
            client,
            _CREATE_BUDGET,
            {"name": "Para deletar", "amount": "50.00", "period": "monthly"},
            token=token,
        )
        budget_id = create_res.get_json()["data"]["createBudget"]["budget"]["id"]

        del_res = _graphql(client, _DELETE_BUDGET, {"budgetId": budget_id}, token=token)
        assert del_res.status_code == 200
        body = del_res.get_json()
        assert "errors" not in body
        assert body["data"]["deleteBudget"]["ok"] is True

    def test_budget_summary_returns_fields(self, client) -> None:
        token = _register_and_login(client, "budget-summary")
        _graphql(
            client,
            _CREATE_BUDGET,
            {"name": "Moradia", "amount": "1000.00", "period": "monthly"},
            token=token,
        )

        res = _graphql(client, _BUDGET_SUMMARY, token=token)
        assert res.status_code == 200
        body = res.get_json()
        assert "errors" not in body
        summary = body["data"]["budgetSummary"]
        assert "totalBudgeted" in summary
        assert "budgetCount" in summary
        assert summary["budgetCount"] >= 1

    def test_create_budget_requires_auth(self, client) -> None:
        res = _graphql(
            client,
            _CREATE_BUDGET,
            {"name": "X", "amount": "100.00", "period": "monthly"},
        )
        assert res.status_code in {200, 401}
        if res.status_code == 200:
            body = res.get_json()
            assert "errors" in body
