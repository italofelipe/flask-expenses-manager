"""
Tests for B20 — GraphQL introspection disabled in production.

Verifies that:
- When FLASK_DEBUG is falsy and GRAPHQL_ALLOW_INTROSPECTION is not explicitly
  set, GraphQLSecurityPolicy.from_env() disables introspection (production default).
- When FLASK_DEBUG is truthy, introspection defaults to enabled (dev default).
- Introspection queries sent against the /graphql endpoint while the policy has
  allow_introspection=False are rejected with GRAPHQL_INTROSPECTION_DISABLED.
- Introspection queries work fine when allow_introspection=True.
"""

from __future__ import annotations

from typing import Any

from app.graphql.security import (
    GRAPHQL_INTROSPECTION_DISABLED,
    GraphQLSecurityPolicy,
)

# ---------------------------------------------------------------------------
# Unit tests: from_env() default behaviour
# ---------------------------------------------------------------------------

_INTROSPECTION_QUERY = "query Introspection { __schema { queryType { name } } }"


def test_from_env_disables_introspection_in_production(monkeypatch) -> None:
    """
    When FLASK_DEBUG is absent/false and GRAPHQL_ALLOW_INTROSPECTION is not set,
    the policy should disable introspection (production-safe default).
    """
    monkeypatch.delenv("GRAPHQL_ALLOW_INTROSPECTION", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)

    policy = GraphQLSecurityPolicy.from_env()

    assert policy.allow_introspection is False


def test_from_env_disables_introspection_when_debug_is_false(monkeypatch) -> None:
    """Explicitly setting FLASK_DEBUG=false still disables introspection."""
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.delenv("GRAPHQL_ALLOW_INTROSPECTION", raising=False)

    policy = GraphQLSecurityPolicy.from_env()

    assert policy.allow_introspection is False


def test_from_env_enables_introspection_in_debug_mode(monkeypatch) -> None:
    """When FLASK_DEBUG=true, introspection should be enabled by default (dev mode)."""
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.delenv("GRAPHQL_ALLOW_INTROSPECTION", raising=False)

    policy = GraphQLSecurityPolicy.from_env()

    assert policy.allow_introspection is True


def test_from_env_explicit_introspection_flag_overrides_debug(monkeypatch) -> None:
    """GRAPHQL_ALLOW_INTROSPECTION takes precedence over FLASK_DEBUG."""
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("GRAPHQL_ALLOW_INTROSPECTION", "false")

    policy = GraphQLSecurityPolicy.from_env()

    assert policy.allow_introspection is False


# ---------------------------------------------------------------------------
# Integration tests: endpoint rejects introspection in production mode
# ---------------------------------------------------------------------------


def _graphql(client: Any, query: str) -> Any:
    return client.post("/graphql", json={"query": query})


def test_introspection_blocked_when_policy_disables_it(client: Any) -> None:
    """
    When the security policy has allow_introspection=False (simulating production),
    an introspection query is rejected with GRAPHQL_INTROSPECTION_DISABLED.
    """
    policy = client.application.extensions.get("graphql_security_policy")
    assert policy is not None

    # Simulate production: disable introspection
    policy.update_limits(allow_introspection=False)

    resp = _graphql(client, _INTROSPECTION_QUERY)

    assert resp.status_code == 400
    body = resp.get_json()
    assert "errors" in body
    assert body["errors"][0]["extensions"]["code"] == GRAPHQL_INTROSPECTION_DISABLED


def test_introspection_allowed_in_dev_mode(client: Any) -> None:
    """
    When allow_introspection=True (dev/test mode), introspection queries succeed.
    The conftest sets GRAPHQL_ALLOW_INTROSPECTION=true so this should pass
    without modification.
    """
    policy = client.application.extensions.get("graphql_security_policy")
    assert policy is not None

    policy.update_limits(allow_introspection=True)

    resp = _graphql(client, _INTROSPECTION_QUERY)

    # The query may return 200 with data, or 401 (auth required on some setups).
    # What matters is that it is NOT rejected for introspection being disabled.
    body = resp.get_json()
    errors = body.get("errors", [])
    introspection_error_codes = [
        err.get("extensions", {}).get("code") for err in errors
    ]
    assert GRAPHQL_INTROSPECTION_DISABLED not in introspection_error_codes
