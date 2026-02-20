from __future__ import annotations

from typing import Any

from app.extensions.integration_metrics import reset_metrics_for_tests, snapshot_metrics
from app.graphql.security import GRAPHQL_DEPTH_LIMIT_EXCEEDED, GraphQLSecurityPolicy


def _graphql(
    client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    token: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload: dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    return client.post("/graphql", json=payload, headers=headers)


def _register_and_login(client: Any, suffix: str) -> str:
    register_mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) {
        message
      }
    }
    """
    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    credentials = {
        "name": f"graphql-observability-{suffix}",
        "email": f"graphql-observability-{suffix}@email.com",
        "password": "StrongPass@123",
    }
    register_response = _graphql(client, register_mutation, credentials)
    assert register_response.status_code == 200
    login_response = _graphql(
        client,
        login_mutation,
        {"email": credentials["email"], "password": credentials["password"]},
    )
    assert login_response.status_code == 200
    return str(login_response.get_json()["data"]["login"]["token"])


def test_graphql_metrics_record_domain_and_cost_for_accepted_query(client: Any) -> None:
    token = _register_and_login(client, "accepted")

    reset_metrics_for_tests()
    response = _graphql(client, "query { me { id email } }", token=token)
    assert response.status_code == 200
    body = response.get_json()
    assert "errors" not in body

    metrics = snapshot_metrics(prefix="graphql.")
    assert metrics["graphql.request.total"] == 1
    assert metrics["graphql.request.accepted"] == 1
    assert metrics.get("graphql.request.rejected", 0) == 0
    assert metrics["graphql.field.me.requests"] == 1
    assert metrics["graphql.domain.user.requests"] == 1
    assert metrics["graphql.request.depth_total"] >= 1
    assert metrics["graphql.request.complexity_total"] >= 1
    assert metrics["graphql.domain.user.complexity_total"] >= 1


def test_graphql_metrics_record_security_violations(client: Any) -> None:
    token = _register_and_login(client, "security")
    with client.application.app_context():
        policy = client.application.extensions.get("graphql_security_policy")
        assert isinstance(policy, GraphQLSecurityPolicy)
        policy.update_limits(max_depth=1)

    reset_metrics_for_tests()
    response = _graphql(client, "query { me { id email } }", token=token)
    assert response.status_code == 400
    error = response.get_json()["errors"][0]
    assert error["extensions"]["code"] == GRAPHQL_DEPTH_LIMIT_EXCEEDED

    metrics = snapshot_metrics(prefix="graphql.")
    assert metrics["graphql.request.total"] == 1
    assert metrics["graphql.request.rejected"] == 1
    assert metrics.get("graphql.request.accepted", 0) == 0
    assert metrics["graphql.security_violation.total"] == 1
    assert metrics["graphql.security_violation.code.graphql_depth_limit_exceeded"] == 1


def test_graphql_metrics_record_authorization_violations(client: Any) -> None:
    reset_metrics_for_tests()
    response = _graphql(client, "query { me { id email } }")
    assert response.status_code == 401
    error = response.get_json()["errors"][0]
    assert error["extensions"]["code"] == "GRAPHQL_AUTH_REQUIRED"

    metrics = snapshot_metrics(prefix="graphql.")
    assert metrics["graphql.request.total"] == 1
    assert metrics["graphql.request.rejected"] == 1
    assert metrics.get("graphql.request.accepted", 0) == 0
    assert metrics["graphql.authorization_violation.total"] == 1
    assert metrics["graphql.authorization_violation.code.graphql_auth_required"] == 1
