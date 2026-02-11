import uuid
from datetime import date
from typing import Any, Dict

from app.graphql.security import (
    GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED,
    GRAPHQL_DEPTH_LIMIT_EXCEEDED,
    GRAPHQL_OPERATION_LIMIT_EXCEEDED,
    GRAPHQL_QUERY_TOO_LARGE,
    GraphQLSecurityPolicy,
)


def _graphql(
    client: Any,
    query: str,
    *,
    variables: Dict[str, Any] | None = None,
    token: str | None = None,
    operation_name: str | None = None,
):
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload: Dict[str, Any] = {"query": query, "variables": variables or {}}
    if operation_name:
        payload["operationName"] = operation_name
    return client.post("/graphql", json=payload, headers=headers)


def _register_and_login(client: Any, *, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={
            "name": f"{prefix}-{suffix}",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return str(login_response.get_json()["token"])


def _policy(client: Any) -> GraphQLSecurityPolicy:
    policy = client.application.extensions.get("graphql_security_policy")
    assert isinstance(policy, GraphQLSecurityPolicy)
    return policy


def test_graphql_rejects_query_exceeding_depth(client: Any) -> None:
    policy = _policy(client)
    policy.update_limits(max_depth=3, max_complexity=10_000, max_query_bytes=20_000)
    token = _register_and_login(client, prefix="graphql-depth")

    query = """
    query Dashboard($month: String!) {
      transactionDashboard(month: $month) {
        counts {
          status {
            paid
          }
        }
      }
    }
    """
    response = _graphql(
        client,
        query,
        variables={"month": date.today().strftime("%Y-%m")},
        token=token,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert "errors" in body
    error = body["errors"][0]
    assert error["extensions"]["code"] == GRAPHQL_DEPTH_LIMIT_EXCEEDED


def test_graphql_rejects_query_exceeding_complexity(client: Any) -> None:
    policy = _policy(client)
    policy.update_limits(max_depth=10, max_complexity=10, max_query_bytes=20_000)
    token = _register_and_login(client, prefix="graphql-complexity")

    query = """
    query Dashboard($month: String!) {
      transactionDashboard(month: $month) {
        totals { incomeTotal expenseTotal balance }
        counts {
          totalTransactions
          incomeTransactions
          expenseTransactions
          status { paid pending cancelled postponed overdue }
        }
        topCategories {
          expense { categoryName totalAmount transactionsCount }
          income { categoryName totalAmount transactionsCount }
        }
      }
    }
    """
    response = _graphql(
        client,
        query,
        variables={"month": date.today().strftime("%Y-%m")},
        token=token,
    )

    assert response.status_code == 400
    body = response.get_json()
    error = body["errors"][0]
    assert error["extensions"]["code"] == GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED


def test_graphql_rejects_document_with_too_many_operations(client: Any) -> None:
    policy = _policy(client)
    policy.update_limits(max_operations=1, max_depth=10, max_complexity=100)

    query = """
    query OperationA { __typename }
    query OperationB { __typename }
    """
    response = _graphql(client, query, operation_name="OperationA")

    assert response.status_code == 400
    body = response.get_json()
    error = body["errors"][0]
    assert error["extensions"]["code"] == GRAPHQL_OPERATION_LIMIT_EXCEEDED


def test_graphql_rejects_query_exceeding_size_limit(client: Any) -> None:
    policy = _policy(client)
    policy.update_limits(
        max_query_bytes=80,
        max_depth=20,
        max_complexity=10_000,
        max_operations=3,
    )
    large_query = (
        "query Large { " + " ".join([f"f{i}: __typename" for i in range(12)]) + " }"
    )
    response = _graphql(client, large_query)

    assert response.status_code == 400
    body = response.get_json()
    error = body["errors"][0]
    assert error["extensions"]["code"] == GRAPHQL_QUERY_TOO_LARGE
