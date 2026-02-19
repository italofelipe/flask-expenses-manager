from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4


def _graphql(
    client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
    token: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


def _register_and_login_graphql(client: Any, suffix: str) -> str:
    register_mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) {
        message
      }
    }
    """
    register_response = _graphql(
        client,
        register_mutation,
        {
            "name": suffix,
            "email": f"{suffix}@email.com",
            "password": "StrongPass@123",
        },
    )
    assert register_response.status_code == 200
    assert "errors" not in register_response.get_json()

    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    login_response = _graphql(
        client,
        login_mutation,
        {"email": f"{suffix}@email.com", "password": "StrongPass@123"},
    )
    assert login_response.status_code == 200
    login_body = login_response.get_json()
    assert "errors" not in login_body
    token = login_body["data"]["login"]["token"]
    assert token
    return token


def _first_error_code(response: Any) -> str:
    body = response.get_json()
    assert body and "errors" in body
    return body["errors"][0]["extensions"]["code"]


def test_graphql_login_invalid_credentials_returns_unauthorized_code(
    client: Any,
) -> None:
    _register_and_login_graphql(client, "graphql-auth-base")
    mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    response = _graphql(
        client,
        mutation,
        variables={"email": "graphql-auth-base@email.com", "password": "wrong"},
    )
    assert response.status_code in {200, 400}
    assert _first_error_code(response) == "UNAUTHORIZED"


def test_graphql_duplicate_ticker_returns_conflict_code(client: Any) -> None:
    token = _register_and_login_graphql(client, "graphql-ticker-conflict")
    mutation = """
    mutation AddTicker($symbol: String!, $quantity: Float!) {
      addTicker(symbol: $symbol, quantity: $quantity) {
        item { id symbol quantity }
      }
    }
    """
    first = _graphql(
        client,
        mutation,
        variables={"symbol": "PETR4", "quantity": 1},
        token=token,
    )
    assert first.status_code == 200
    assert "errors" not in first.get_json()

    second = _graphql(
        client,
        mutation,
        variables={"symbol": "PETR4", "quantity": 1},
        token=token,
    )
    assert second.status_code in {200, 400}
    assert _first_error_code(second) == "CONFLICT"


def test_graphql_wallet_validation_returns_validation_code(client: Any) -> None:
    token = _register_and_login_graphql(client, "graphql-wallet-validation")
    mutation = """
    mutation AddWallet($registerDate: String!) {
      addWalletEntry(
        name: "Reserva",
        value: 1000,
        registerDate: $registerDate,
        shouldBeOnWallet: true
      ) {
        item { id }
      }
    }
    """
    response = _graphql(
        client,
        mutation,
        variables={"registerDate": "2026/02/19"},
        token=token,
    )
    assert response.status_code in {200, 400}
    assert _first_error_code(response) == "VALIDATION_ERROR"


def test_graphql_transaction_delete_forbidden_returns_forbidden_code(
    client: Any,
) -> None:
    owner_token = _register_and_login_graphql(client, "graphql-tx-owner")
    intruder_token = _register_and_login_graphql(client, "graphql-tx-intruder")

    create_mutation = """
    mutation CreateTx($dueDate: String!) {
      createTransaction(
        title: "Conta",
        amount: "100.00",
        type: "expense",
        dueDate: $dueDate
      ) {
        items { id }
      }
    }
    """
    create_response = _graphql(
        client,
        create_mutation,
        variables={"dueDate": date.today().isoformat()},
        token=owner_token,
    )
    assert create_response.status_code == 200
    create_body = create_response.get_json()
    assert "errors" not in create_body
    transaction_id = create_body["data"]["createTransaction"]["items"][0]["id"]

    delete_mutation = """
    mutation DeleteTx($transactionId: UUID!) {
      deleteTransaction(transactionId: $transactionId) {
        ok
        message
      }
    }
    """
    delete_response = _graphql(
        client,
        delete_mutation,
        variables={"transactionId": transaction_id},
        token=intruder_token,
    )
    assert delete_response.status_code in {200, 400}
    assert _first_error_code(delete_response) == "FORBIDDEN"


def test_graphql_investment_not_found_returns_not_found_code(client: Any) -> None:
    token = _register_and_login_graphql(client, "graphql-investment-not-found")
    query = """
    query Summary($investmentId: UUID!) {
      investmentOperationSummary(investmentId: $investmentId) {
        totalOperations
      }
    }
    """
    response = _graphql(
        client,
        query,
        variables={"investmentId": str(uuid4())},
        token=token,
    )
    assert response.status_code in {200, 400}
    assert _first_error_code(response) == "NOT_FOUND"
