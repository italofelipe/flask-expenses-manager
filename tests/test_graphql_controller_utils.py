from __future__ import annotations

from types import SimpleNamespace

import pytest
from graphql import GraphQLError

from app.controllers import graphql_controller
from app.controllers.graphql_controller_utils import (
    build_graphql_result_response,
    graphql_error_response,
    parse_graphql_payload,
)
from app.graphql.authorization import GraphQLAuthorizationPolicy
from app.graphql.security import GraphQLSecurityPolicy


def test_parse_graphql_payload_and_error_response_helpers() -> None:
    query, variables, operation_name = parse_graphql_payload(
        {"query": "query { __typename }", "variables": {"a": 1}, "operationName": "Q"}
    )
    assert query == "query { __typename }"
    assert variables == {"a": 1}
    assert operation_name == "Q"

    with pytest.raises(ValueError):
        parse_graphql_payload({"query": ""})
    with pytest.raises(ValueError):
        parse_graphql_payload({"query": "query { __typename }", "variables": []})
    with pytest.raises(ValueError):
        parse_graphql_payload(
            {"query": "query { __typename }", "operationName": {"name": "Q"}}
        )

    error_payload, error_status = graphql_error_response(
        message="Boom",
        code="VALIDATION_ERROR",
        details={"field": "query"},
        status_code=422,
    )
    assert error_status == 422
    assert error_payload["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

    plain_payload, plain_status = graphql_error_response(message="Bad request")
    assert plain_status == 400
    assert "extensions" not in plain_payload["errors"][0]


def test_build_graphql_result_response_helper() -> None:
    ok_result = SimpleNamespace(data={"ping": "pong"}, errors=None)
    payload_ok, status_ok = build_graphql_result_response(
        ok_result, format_error=lambda err: {"message": err.message}
    )
    assert status_ok == 200
    assert payload_ok == {"data": {"ping": "pong"}}

    fail_result = SimpleNamespace(data=None, errors=[GraphQLError("failure")])
    payload_fail, status_fail = build_graphql_result_response(
        fail_result, format_error=lambda err: {"message": err.message}
    )
    assert status_fail == 400
    assert payload_fail["errors"][0]["message"] == "failure"


def test_graphql_controller_fallback_policy_resolution(app) -> None:
    with app.app_context():
        app.extensions.pop("graphql_security_policy", None)
        app.extensions.pop("graphql_authorization_policy", None)

        security_policy = graphql_controller._get_security_policy()
        authorization_policy = graphql_controller._get_authorization_policy()

        assert isinstance(security_policy, GraphQLSecurityPolicy)
        assert isinstance(authorization_policy, GraphQLAuthorizationPolicy)
        assert app.extensions["graphql_security_policy"] is security_policy
        assert app.extensions["graphql_authorization_policy"] is authorization_policy


def test_execute_graphql_rejects_invalid_payload_shape(client) -> None:
    response = client.post(
        "/graphql",
        json={"query": "query { __typename }", "variables": ["invalid"]},
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["errors"][0]["message"] == "Campo 'variables' deve ser um objeto."
