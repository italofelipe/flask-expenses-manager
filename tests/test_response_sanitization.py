from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from graphql import GraphQLError

from app.utils.response_builder import error_payload, success_payload


def test_success_payload_removes_sensitive_fields() -> None:
    payload = success_payload(
        message="ok",
        data={
            "user": {
                "email": "test@email.com",
                "password": "secret",
                "nested": {"password_hash": "hash"},
            },
            "items": [{"secret_key": "s"}, {"value": 10}],
        },
    )

    assert payload["data"]["user"]["email"] == "test@email.com"
    assert "password" not in payload["data"]["user"]
    assert "password_hash" not in payload["data"]["user"]["nested"]
    assert "secret_key" not in payload["data"]["items"][0]


def test_error_payload_redacts_internal_details_outside_debug(app: Any) -> None:
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    with app.app_context():
        payload = error_payload(
            message="Erro interno",
            code="INTERNAL_ERROR",
            details={
                "request_id": "abc-123",
                "exception": "db password leaked",
                "traceback": "stack",
            },
        )
    assert payload["error"]["details"] == {"request_id": "abc-123"}


@dataclass
class _FakeExecutionResult:
    errors: list[GraphQLError]
    data: dict[str, Any] | None


def test_graphql_masks_internal_errors_in_production(
    app: Any,
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.config["DEBUG"] = False
    app.config["TESTING"] = False

    from app.controllers import graphql_controller

    def _fake_execute(*args: Any, **kwargs: Any) -> _FakeExecutionResult:
        error = GraphQLError(
            "database password leaked",
            original_error=RuntimeError("secret failure"),
        )
        return _FakeExecutionResult(errors=[error], data=None)

    monkeypatch.setattr(graphql_controller.schema, "execute", _fake_execute)

    response = client.post("/graphql", json={"query": "query { __typename }"})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["errors"][0]["message"] == "An unexpected error occurred."
    assert payload["errors"][0]["extensions"]["code"] == "INTERNAL_ERROR"


def test_graphql_keeps_public_error_with_allowlisted_code_in_production(
    app: Any,
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.config["DEBUG"] = False
    app.config["TESTING"] = False

    from app.controllers import graphql_controller

    def _fake_execute(*args: Any, **kwargs: Any) -> _FakeExecutionResult:
        error = GraphQLError(
            "Invalid credentials",
            extensions={"code": "UNAUTHORIZED"},
            original_error=GraphQLError("Invalid credentials"),
        )
        return _FakeExecutionResult(errors=[error], data=None)

    monkeypatch.setattr(graphql_controller.schema, "execute", _fake_execute)

    response = client.post("/graphql", json={"query": "query { __typename }"})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["errors"][0]["message"] == "Invalid credentials"
    assert payload["errors"][0]["extensions"]["code"] == "UNAUTHORIZED"
