from __future__ import annotations

from typing import Any

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
    GRAPHQL_QUERY_TOO_LARGE,
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
)
from app.graphql.introspection_policy import enforce_introspection_policy

__all__ = [
    "GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED",
    "GRAPHQL_DEPTH_LIMIT_EXCEEDED",
    "GRAPHQL_INTROSPECTION_DISABLED",
    "GRAPHQL_OPERATION_LIMIT_EXCEEDED",
    "GRAPHQL_OPERATION_NOT_FOUND",
    "GRAPHQL_QUERY_TOO_LARGE",
    "GraphQLQueryMetrics",
    "GraphQLSecurityPolicy",
    "GraphQLSecurityViolation",
    "analyze_graphql_query",
]

# Private aliases kept for backwards compatibility with private imports in tests
_parse_document = parse_document
_collect_fragments_and_operations = collect_fragments_and_operations
_ensure_operation_count_within_limit = ensure_operation_count_within_limit
_select_operations_to_analyze = select_operations_to_analyze
_enforce_depth_and_complexity_limits = enforce_depth_and_complexity_limits
_enforce_introspection_policy = enforce_introspection_policy


def analyze_graphql_query(
    *,
    query: str,
    operation_name: str | None,
    variable_values: dict[str, Any] | None,
    policy: GraphQLSecurityPolicy,
) -> GraphQLQueryMetrics:
    query_bytes = len(query.encode("utf-8"))
    if query_bytes > policy.max_query_bytes:
        raise GraphQLSecurityViolation(
            code=GRAPHQL_QUERY_TOO_LARGE,
            message=(
                "Query GraphQL excedeu o tamanho máximo permitido "
                f"({policy.max_query_bytes} bytes)."
            ),
            details={
                "query_bytes": query_bytes,
                "max_query_bytes": policy.max_query_bytes,
            },
        )

    document = parse_document(query)
    fragments, operations = collect_fragments_and_operations(document)
    ensure_operation_count_within_limit(operations, policy)
    selected_operations = select_operations_to_analyze(operations, operation_name)
    enforce_introspection_policy(selected_operations, policy)
    metrics = calculate_metrics(
        selected_operations,
        fragments=fragments,
        variable_values=variable_values,
        max_list_multiplier=policy.max_list_multiplier,
        query=query,
    )
    enforce_depth_and_complexity_limits(metrics, policy)
    return GraphQLQueryMetrics(
        operation_count=len(operations),
        depth=metrics.depth,
        complexity=metrics.complexity,
        query_bytes=query_bytes,
        root_fields=metrics.root_fields,
    )
