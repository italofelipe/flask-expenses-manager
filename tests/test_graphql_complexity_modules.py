"""Unit tests for the extracted graphql/complexity/ modules and introspection_policy."""

from __future__ import annotations

import pytest
from graphql import parse
from graphql.language import ast

from app.graphql.complexity.analyzer import (
    GraphQLQueryMetrics,
    calculate_metrics,
    collect_fragments_and_operations,
    enforce_depth_and_complexity_limits,
    ensure_operation_count_within_limit,
    parse_document,
    select_operations_to_analyze,
)
from app.graphql.complexity.policy import (
    GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED,
    GRAPHQL_DEPTH_LIMIT_EXCEEDED,
    GRAPHQL_INTROSPECTION_DISABLED,
    GRAPHQL_OPERATION_LIMIT_EXCEEDED,
    GRAPHQL_OPERATION_NOT_FOUND,
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
    _read_bool_env,
    _read_int_env,
)
from app.graphql.introspection_policy import (
    _contains_introspection_field,
    enforce_introspection_policy,
)

# ---------------------------------------------------------------------------
# policy.py — env helpers
# ---------------------------------------------------------------------------


class TestReadIntEnv:
    def test_returns_default_when_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert _read_int_env("TEST_VAR", 42) == 42

    def test_parses_valid_integer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR", "100")
        assert _read_int_env("TEST_VAR", 42) == 100

    def test_returns_default_on_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_VAR", "not_a_number")
        assert _read_int_env("TEST_VAR", 42) == 42

    def test_returns_default_when_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR", "0")
        assert _read_int_env("TEST_VAR", 42) == 42

    def test_returns_default_when_negative(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_VAR", "-5")
        assert _read_int_env("TEST_VAR", 42) == 42


class TestReadBoolEnv:
    def test_returns_default_when_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert _read_bool_env("TEST_FLAG", False) is False
        assert _read_bool_env("TEST_FLAG", True) is True

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "True"])
    def test_truthy_values(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("TEST_FLAG", value)
        assert _read_bool_env("TEST_FLAG", False) is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_falsy_values(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("TEST_FLAG", value)
        assert _read_bool_env("TEST_FLAG", True) is False


# ---------------------------------------------------------------------------
# policy.py — GraphQLSecurityPolicy
# ---------------------------------------------------------------------------


class TestGraphQLSecurityPolicy:
    def test_from_env_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in [
            "GRAPHQL_MAX_QUERY_BYTES",
            "GRAPHQL_MAX_DEPTH",
            "GRAPHQL_MAX_COMPLEXITY",
            "GRAPHQL_MAX_OPERATIONS",
            "GRAPHQL_MAX_LIST_MULTIPLIER",
            "GRAPHQL_ALLOW_INTROSPECTION",
            "FLASK_DEBUG",
        ]:
            monkeypatch.delenv(var, raising=False)
        policy = GraphQLSecurityPolicy.from_env()
        assert policy.max_query_bytes == 20_000
        assert policy.max_depth == 8
        assert policy.max_complexity == 300
        assert policy.max_operations == 3
        assert policy.max_list_multiplier == 50
        assert policy.allow_introspection is False

    def test_update_limits_clamps_minimum_to_one(self) -> None:
        policy = GraphQLSecurityPolicy(
            max_query_bytes=1000,
            max_depth=5,
            max_complexity=100,
            max_operations=2,
            max_list_multiplier=10,
            allow_introspection=False,
        )
        policy.update_limits(max_depth=0, max_complexity=-5)
        assert policy.max_depth == 1
        assert policy.max_complexity == 1

    def test_update_limits_sets_values(self) -> None:
        policy = GraphQLSecurityPolicy(
            max_query_bytes=1000,
            max_depth=5,
            max_complexity=100,
            max_operations=2,
            max_list_multiplier=10,
            allow_introspection=False,
        )
        policy.update_limits(max_depth=15, allow_introspection=True)
        assert policy.max_depth == 15
        assert policy.allow_introspection is True


# ---------------------------------------------------------------------------
# analyzer.py — parse_document
# ---------------------------------------------------------------------------


class TestParseDocument:
    def test_parses_valid_query(self) -> None:
        doc = parse_document("{ __typename }")
        assert isinstance(doc, ast.DocumentNode)

    def test_raises_violation_on_invalid_query(self) -> None:
        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            parse_document("{ invalid {{ syntax")
        assert exc_info.value.code == "GRAPHQL_PARSE_ERROR"


# ---------------------------------------------------------------------------
# analyzer.py — collect_fragments_and_operations
# ---------------------------------------------------------------------------


class TestCollectFragmentsAndOperations:
    def test_separates_fragments_and_operations(self) -> None:
        doc = parse(
            """
            fragment F on Query { __typename }
            query Q { __typename }
            """
        )
        fragments, operations = collect_fragments_and_operations(doc)
        assert "F" in fragments
        assert len(operations) == 1

    def test_empty_document(self) -> None:
        doc = parse("{ __typename }")
        fragments, operations = collect_fragments_and_operations(doc)
        assert fragments == {}
        assert len(operations) == 1


# ---------------------------------------------------------------------------
# analyzer.py — ensure_operation_count_within_limit
# ---------------------------------------------------------------------------


class TestEnsureOperationCountWithinLimit:
    def _make_policy(self, max_operations: int) -> GraphQLSecurityPolicy:
        return GraphQLSecurityPolicy(
            max_query_bytes=20_000,
            max_depth=8,
            max_complexity=300,
            max_operations=max_operations,
            max_list_multiplier=50,
            allow_introspection=False,
        )

    def test_passes_when_within_limit(self) -> None:
        doc = parse("query A { __typename } query B { __typename }")
        _, operations = collect_fragments_and_operations(doc)
        ensure_operation_count_within_limit(operations, self._make_policy(3))

    def test_raises_when_exceeds_limit(self) -> None:
        doc = parse(
            "query A { __typename } query B { __typename } query C { __typename }"
        )
        _, operations = collect_fragments_and_operations(doc)
        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            ensure_operation_count_within_limit(operations, self._make_policy(2))
        assert exc_info.value.code == GRAPHQL_OPERATION_LIMIT_EXCEEDED


# ---------------------------------------------------------------------------
# analyzer.py — select_operations_to_analyze
# ---------------------------------------------------------------------------


class TestSelectOperationsToAnalyze:
    def test_returns_all_when_no_name(self) -> None:
        doc = parse("query A { __typename } query B { __typename }")
        _, operations = collect_fragments_and_operations(doc)
        selected = select_operations_to_analyze(operations, None)
        assert len(selected) == 2

    def test_selects_by_name(self) -> None:
        doc = parse("query A { __typename } query B { __typename }")
        _, operations = collect_fragments_and_operations(doc)
        selected = select_operations_to_analyze(operations, "A")
        assert len(selected) == 1
        assert selected[0].name and selected[0].name.value == "A"

    def test_raises_when_name_not_found(self) -> None:
        doc = parse("query A { __typename }")
        _, operations = collect_fragments_and_operations(doc)
        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            select_operations_to_analyze(operations, "Z")
        assert exc_info.value.code == GRAPHQL_OPERATION_NOT_FOUND


# ---------------------------------------------------------------------------
# analyzer.py — calculate_metrics
# ---------------------------------------------------------------------------


class TestCalculateMetrics:
    def _policy_kwargs(self) -> dict:
        return dict(
            max_query_bytes=20_000,
            max_depth=8,
            max_complexity=300,
            max_operations=3,
            max_list_multiplier=50,
            allow_introspection=False,
        )

    def test_flat_query_depth_one(self) -> None:
        query = "{ __typename }"
        doc = parse(query)
        fragments, operations = collect_fragments_and_operations(doc)
        metrics = calculate_metrics(
            operations,
            fragments=fragments,
            variable_values=None,
            max_list_multiplier=50,
            query=query,
        )
        assert metrics.depth == 1
        assert metrics.complexity >= 1

    def test_nested_query_increases_depth(self) -> None:
        query = "{ a { b { c } } }"
        doc = parse(query)
        fragments, operations = collect_fragments_and_operations(doc)
        metrics = calculate_metrics(
            operations,
            fragments=fragments,
            variable_values=None,
            max_list_multiplier=50,
            query=query,
        )
        assert metrics.depth == 3

    def test_root_fields_captured(self) -> None:
        query = "{ foo bar }"
        doc = parse(query)
        fragments, operations = collect_fragments_and_operations(doc)
        metrics = calculate_metrics(
            operations,
            fragments=fragments,
            variable_values=None,
            max_list_multiplier=50,
            query=query,
        )
        assert "foo" in metrics.root_fields
        assert "bar" in metrics.root_fields


# ---------------------------------------------------------------------------
# analyzer.py — enforce_depth_and_complexity_limits
# ---------------------------------------------------------------------------


class TestEnforceDepthAndComplexityLimits:
    def _policy(
        self, max_depth: int = 8, max_complexity: int = 300
    ) -> GraphQLSecurityPolicy:
        return GraphQLSecurityPolicy(
            max_query_bytes=20_000,
            max_depth=max_depth,
            max_complexity=max_complexity,
            max_operations=3,
            max_list_multiplier=50,
            allow_introspection=False,
        )

    def test_passes_within_limits(self) -> None:
        metrics = GraphQLQueryMetrics(
            operation_count=1, depth=3, complexity=10, query_bytes=50
        )
        enforce_depth_and_complexity_limits(metrics, self._policy())

    def test_raises_on_depth_exceeded(self) -> None:
        metrics = GraphQLQueryMetrics(
            operation_count=1, depth=9, complexity=10, query_bytes=50
        )
        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            enforce_depth_and_complexity_limits(metrics, self._policy(max_depth=8))
        assert exc_info.value.code == GRAPHQL_DEPTH_LIMIT_EXCEEDED

    def test_raises_on_complexity_exceeded(self) -> None:
        metrics = GraphQLQueryMetrics(
            operation_count=1, depth=3, complexity=301, query_bytes=50
        )
        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            enforce_depth_and_complexity_limits(
                metrics, self._policy(max_complexity=300)
            )
        assert exc_info.value.code == GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED


# ---------------------------------------------------------------------------
# introspection_policy.py
# ---------------------------------------------------------------------------


class TestContainsIntrospectionField:
    def test_detects_schema_introspection(self) -> None:
        doc = parse("{ __schema { types { name } } }")
        _, operations = collect_fragments_and_operations(doc)
        assert _contains_introspection_field(operations[0].selection_set) is True

    def test_detects_type_introspection(self) -> None:
        doc = parse('{ __type(name: "User") { name } }')
        _, operations = collect_fragments_and_operations(doc)
        assert _contains_introspection_field(operations[0].selection_set) is True

    def test_returns_false_for_normal_query(self) -> None:
        doc = parse("{ __typename }")
        _, operations = collect_fragments_and_operations(doc)
        assert _contains_introspection_field(operations[0].selection_set) is False

    def test_returns_false_for_none(self) -> None:
        assert _contains_introspection_field(None) is False


class TestEnforceIntrospectionPolicy:
    def _policy(self, allow: bool) -> GraphQLSecurityPolicy:
        return GraphQLSecurityPolicy(
            max_query_bytes=20_000,
            max_depth=8,
            max_complexity=300,
            max_operations=3,
            max_list_multiplier=50,
            allow_introspection=allow,
        )

    def test_allows_introspection_when_enabled(self) -> None:
        doc = parse("{ __schema { types { name } } }")
        _, operations = collect_fragments_and_operations(doc)
        enforce_introspection_policy(operations, self._policy(allow=True))

    def test_blocks_introspection_when_disabled(self) -> None:
        doc = parse("{ __schema { types { name } } }")
        _, operations = collect_fragments_and_operations(doc)
        with pytest.raises(GraphQLSecurityViolation) as exc_info:
            enforce_introspection_policy(operations, self._policy(allow=False))
        assert exc_info.value.code == GRAPHQL_INTROSPECTION_DISABLED

    def test_passes_normal_query_when_introspection_disabled(self) -> None:
        doc = parse("{ __typename }")
        _, operations = collect_fragments_and_operations(doc)
        enforce_introspection_policy(operations, self._policy(allow=False))
