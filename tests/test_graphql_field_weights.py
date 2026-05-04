"""Tests for per-field complexity weights in GraphQLSecurityPolicy."""

from __future__ import annotations

import json

import pytest

from app.graphql.complexity.policy import _DEFAULT_FIELD_WEIGHTS
from app.graphql.security import (
    GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED,
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
    analyze_graphql_query,
)


def _policy(
    max_complexity: int = 300,
    field_weights: dict[str, int] | None = None,
) -> GraphQLSecurityPolicy:
    return GraphQLSecurityPolicy(
        max_query_bytes=20_000,
        max_depth=8,
        max_complexity=max_complexity,
        max_operations=3,
        max_list_multiplier=50,
        allow_introspection=False,
        field_weights=field_weights
        if field_weights is not None
        else dict(_DEFAULT_FIELD_WEIGHTS),
    )


class TestDefaultFieldWeights:
    def test_default_weights_include_expensive_resolvers(self) -> None:
        assert _DEFAULT_FIELD_WEIGHTS["investmentValuation"] >= 5
        assert _DEFAULT_FIELD_WEIGHTS["portfolioValuation"] >= 5
        assert _DEFAULT_FIELD_WEIGHTS["portfolioValuationHistory"] >= 5
        assert _DEFAULT_FIELD_WEIGHTS["billingPlans"] >= 5

    def test_policy_uses_default_weights_when_not_specified(self) -> None:
        policy = GraphQLSecurityPolicy(
            max_query_bytes=20_000,
            max_depth=8,
            max_complexity=300,
            max_operations=3,
            max_list_multiplier=50,
            allow_introspection=False,
        )
        assert policy.field_weights["investmentValuation"] >= 5

    def test_from_env_loads_default_weights(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GRAPHQL_FIELD_WEIGHTS_JSON", raising=False)
        policy = GraphQLSecurityPolicy.from_env()
        assert "investmentValuation" in policy.field_weights
        assert policy.field_weights["investmentValuation"] >= 5


class TestFieldWeightInComplexityCalculation:
    def test_weighted_field_costs_more_than_plain_field(self) -> None:
        expensive_query = "{ investmentValuation { amount } }"

        weights = {"investmentValuation": 10}
        policy_with_weights = _policy(field_weights=weights)
        policy_no_weights = _policy(field_weights={})

        metrics_expensive_weighted = analyze_graphql_query(
            query=expensive_query,
            operation_name=None,
            variable_values=None,
            policy=policy_with_weights,
        )
        metrics_expensive_no_weights = analyze_graphql_query(
            query=expensive_query,
            operation_name=None,
            variable_values=None,
            policy=policy_no_weights,
        )

        assert (
            metrics_expensive_weighted.complexity
            > metrics_expensive_no_weights.complexity
        )

    def test_weighted_field_triggers_complexity_limit(self) -> None:
        query = "{ investmentValuation { amount } }"
        # set max_complexity so that the weighted field exceeds it
        policy = _policy(max_complexity=5, field_weights={"investmentValuation": 10})

        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            analyze_graphql_query(
                query=query,
                operation_name=None,
                variable_values=None,
                policy=policy,
            )
        assert exc_info.value.code == GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED

    def test_same_field_no_weight_passes_lower_limit(self) -> None:
        query = "{ investmentValuation { amount } }"
        # no field weights → default cost 1, which is below limit of 5
        policy = _policy(max_complexity=5, field_weights={})

        metrics = analyze_graphql_query(
            query=query,
            operation_name=None,
            variable_values=None,
            policy=policy,
        )
        assert metrics.complexity <= 5

    def test_weight_one_is_default_for_unknown_fields(self) -> None:
        query = "{ __typename }"
        policy = _policy(field_weights={})

        metrics = analyze_graphql_query(
            query=query,
            operation_name=None,
            variable_values=None,
            policy=policy,
        )
        assert metrics.complexity == 1

    def test_multiple_expensive_fields_accumulate_cost(self) -> None:
        query = "{ investmentValuation { amount } portfolioValuation { total } }"
        weights = {"investmentValuation": 10, "portfolioValuation": 10}
        # each root field cost 10 base + 1 scalar = 11; total > 5
        policy = _policy(max_complexity=15, field_weights=weights)

        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            analyze_graphql_query(
                query=query,
                operation_name=None,
                variable_values=None,
                policy=policy,
            )
        assert exc_info.value.code == GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED


class TestUpdateLimitsFieldWeights:
    def test_update_limits_can_override_field_weights(self) -> None:
        policy = _policy(field_weights={"myField": 5})
        policy.update_limits(field_weights={"myField": 20})
        assert policy.field_weights["myField"] == 20

    def test_update_limits_clamps_weight_minimum_to_one(self) -> None:
        policy = _policy(field_weights={"myField": 5})
        policy.update_limits(field_weights={"myField": 0})
        assert policy.field_weights["myField"] == 1


class TestReadFieldWeightsEnv:
    def test_env_var_overrides_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        custom = json.dumps({"myCustomField": 99})
        monkeypatch.setenv("GRAPHQL_FIELD_WEIGHTS_JSON", custom)
        policy = GraphQLSecurityPolicy.from_env()
        assert policy.field_weights.get("myCustomField") == 99

    def test_invalid_json_falls_back_to_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRAPHQL_FIELD_WEIGHTS_JSON", "not_valid_json")
        policy = GraphQLSecurityPolicy.from_env()
        assert "investmentValuation" in policy.field_weights

    def test_empty_env_var_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GRAPHQL_FIELD_WEIGHTS_JSON", "")
        policy = GraphQLSecurityPolicy.from_env()
        assert "investmentValuation" in policy.field_weights
