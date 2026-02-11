from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from graphql import GraphQLError, parse
from graphql.language import ast

GRAPHQL_QUERY_TOO_LARGE = "GRAPHQL_QUERY_TOO_LARGE"
GRAPHQL_DEPTH_LIMIT_EXCEEDED = "GRAPHQL_DEPTH_LIMIT_EXCEEDED"
GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED = "GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED"
GRAPHQL_OPERATION_LIMIT_EXCEEDED = "GRAPHQL_OPERATION_LIMIT_EXCEEDED"
GRAPHQL_OPERATION_NOT_FOUND = "GRAPHQL_OPERATION_NOT_FOUND"
GRAPHQL_INTROSPECTION_DISABLED = "GRAPHQL_INTROSPECTION_DISABLED"

_LIST_ARGUMENT_NAMES = {
    "first",
    "last",
    "limit",
    "perPage",
    "per_page",
    "pageSize",
    "size",
}


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class GraphQLSecurityPolicy:
    max_query_bytes: int
    max_depth: int
    max_complexity: int
    max_operations: int
    max_list_multiplier: int
    allow_introspection: bool

    @classmethod
    def from_env(cls) -> "GraphQLSecurityPolicy":
        default_introspection = _read_bool_env("FLASK_DEBUG", False)
        return cls(
            max_query_bytes=_read_int_env("GRAPHQL_MAX_QUERY_BYTES", 20_000),
            max_depth=_read_int_env("GRAPHQL_MAX_DEPTH", 8),
            max_complexity=_read_int_env("GRAPHQL_MAX_COMPLEXITY", 300),
            max_operations=_read_int_env("GRAPHQL_MAX_OPERATIONS", 3),
            max_list_multiplier=_read_int_env("GRAPHQL_MAX_LIST_MULTIPLIER", 50),
            allow_introspection=_read_bool_env(
                "GRAPHQL_ALLOW_INTROSPECTION",
                default_introspection,
            ),
        )

    def update_limits(
        self,
        *,
        max_query_bytes: int | None = None,
        max_depth: int | None = None,
        max_complexity: int | None = None,
        max_operations: int | None = None,
        max_list_multiplier: int | None = None,
        allow_introspection: bool | None = None,
    ) -> None:
        if max_query_bytes is not None:
            self.max_query_bytes = max(max_query_bytes, 1)
        if max_depth is not None:
            self.max_depth = max(max_depth, 1)
        if max_complexity is not None:
            self.max_complexity = max(max_complexity, 1)
        if max_operations is not None:
            self.max_operations = max(max_operations, 1)
        if max_list_multiplier is not None:
            self.max_list_multiplier = max(max_list_multiplier, 1)
        if allow_introspection is not None:
            self.allow_introspection = bool(allow_introspection)


@dataclass(frozen=True)
class GraphQLQueryMetrics:
    operation_count: int
    depth: int
    complexity: int
    query_bytes: int


@dataclass(frozen=True)
class GraphQLSecurityViolation(Exception):
    code: str
    message: str
    details: dict[str, Any]


def _resolve_int_value(
    value_node: ast.ValueNode,
    variable_values: dict[str, Any] | None,
) -> int | None:
    if isinstance(value_node, ast.IntValueNode):
        try:
            return int(value_node.value)
        except ValueError:
            return None

    if isinstance(value_node, ast.VariableNode) and isinstance(variable_values, dict):
        raw_value = variable_values.get(value_node.name.value)
        if isinstance(raw_value, bool):
            return None
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, str) and raw_value.isdigit():
            return int(raw_value)
    return None


def _resolve_field_multiplier(
    field_node: ast.FieldNode,
    variable_values: dict[str, Any] | None,
    max_list_multiplier: int,
) -> int:
    for argument in field_node.arguments or []:
        if argument.name.value not in _LIST_ARGUMENT_NAMES:
            continue
        resolved_value = _resolve_int_value(argument.value, variable_values)
        if resolved_value is None:
            continue
        if resolved_value <= 0:
            return 1
        return min(resolved_value, max_list_multiplier)
    return 1


def _analyze_selection_set(
    selection_set: ast.SelectionSetNode,
    *,
    current_depth: int,
    fragments: dict[str, ast.FragmentDefinitionNode],
    variable_values: dict[str, Any] | None,
    max_list_multiplier: int,
    visited_fragments: set[str],
) -> tuple[int, int]:
    max_depth = current_depth
    complexity = 0

    for selection in selection_set.selections:
        if isinstance(selection, ast.FieldNode):
            field_depth = current_depth + 1
            field_complexity = 1

            if selection.selection_set:
                nested_depth, nested_complexity = _analyze_selection_set(
                    selection.selection_set,
                    current_depth=field_depth,
                    fragments=fragments,
                    variable_values=variable_values,
                    max_list_multiplier=max_list_multiplier,
                    visited_fragments=visited_fragments.copy(),
                )
                multiplier = _resolve_field_multiplier(
                    selection, variable_values, max_list_multiplier
                )
                field_depth = max(field_depth, nested_depth)
                field_complexity += nested_complexity * multiplier

            max_depth = max(max_depth, field_depth)
            complexity += field_complexity
            continue

        if isinstance(selection, ast.InlineFragmentNode) and selection.selection_set:
            nested_depth, nested_complexity = _analyze_selection_set(
                selection.selection_set,
                current_depth=current_depth,
                fragments=fragments,
                variable_values=variable_values,
                max_list_multiplier=max_list_multiplier,
                visited_fragments=visited_fragments.copy(),
            )
            max_depth = max(max_depth, nested_depth)
            complexity += nested_complexity
            continue

        if isinstance(selection, ast.FragmentSpreadNode):
            fragment_name = selection.name.value
            if fragment_name in visited_fragments:
                continue
            fragment_node = fragments.get(fragment_name)
            if fragment_node is None:
                continue
            next_visited = visited_fragments.copy()
            next_visited.add(fragment_name)
            nested_depth, nested_complexity = _analyze_selection_set(
                fragment_node.selection_set,
                current_depth=current_depth,
                fragments=fragments,
                variable_values=variable_values,
                max_list_multiplier=max_list_multiplier,
                visited_fragments=next_visited,
            )
            max_depth = max(max_depth, nested_depth)
            complexity += nested_complexity

    return max_depth, complexity


def _parse_document(query: str) -> ast.DocumentNode:
    try:
        return parse(query)
    except GraphQLError as exc:
        raise GraphQLSecurityViolation(
            code="GRAPHQL_PARSE_ERROR",
            message=f"Query GraphQL inválida: {exc.message}",
            details={},
        ) from exc


def _collect_fragments_and_operations(
    document: ast.DocumentNode,
) -> tuple[dict[str, ast.FragmentDefinitionNode], list[ast.OperationDefinitionNode]]:
    fragments: dict[str, ast.FragmentDefinitionNode] = {}
    operations: list[ast.OperationDefinitionNode] = []
    for definition in document.definitions:
        if isinstance(definition, ast.FragmentDefinitionNode):
            fragments[definition.name.value] = definition
        if isinstance(definition, ast.OperationDefinitionNode):
            operations.append(definition)
    return fragments, operations


def _ensure_operation_count_within_limit(
    operations: list[ast.OperationDefinitionNode],
    policy: GraphQLSecurityPolicy,
) -> None:
    operation_count = len(operations)
    if operation_count <= policy.max_operations:
        return
    raise GraphQLSecurityViolation(
        code=GRAPHQL_OPERATION_LIMIT_EXCEEDED,
        message=(
            "Quantidade de operações GraphQL excedeu o limite permitido "
            f"({policy.max_operations})."
        ),
        details={
            "operation_count": operation_count,
            "max_operations": policy.max_operations,
        },
    )


def _select_operations_to_analyze(
    operations: list[ast.OperationDefinitionNode],
    operation_name: str | None,
) -> list[ast.OperationDefinitionNode]:
    if not operation_name:
        return operations

    selected_operations = [
        operation
        for operation in operations
        if operation.name and operation.name.value == operation_name
    ]
    if selected_operations:
        return selected_operations

    raise GraphQLSecurityViolation(
        code=GRAPHQL_OPERATION_NOT_FOUND,
        message=f"Operação '{operation_name}' não encontrada no documento.",
        details={"operation_name": operation_name},
    )


def _calculate_metrics(
    operations: list[ast.OperationDefinitionNode],
    *,
    fragments: dict[str, ast.FragmentDefinitionNode],
    variable_values: dict[str, Any] | None,
    max_list_multiplier: int,
    query: str,
) -> GraphQLQueryMetrics:
    max_depth = 0
    total_complexity = 0
    for operation in operations:
        operation_depth, operation_complexity = _analyze_selection_set(
            operation.selection_set,
            current_depth=0,
            fragments=fragments,
            variable_values=variable_values,
            max_list_multiplier=max_list_multiplier,
            visited_fragments=set(),
        )
        max_depth = max(max_depth, operation_depth)
        total_complexity += operation_complexity

    return GraphQLQueryMetrics(
        operation_count=len(operations),
        depth=max_depth,
        complexity=total_complexity,
        query_bytes=len(query.encode("utf-8")),
    )


def _enforce_depth_and_complexity_limits(
    metrics: GraphQLQueryMetrics,
    policy: GraphQLSecurityPolicy,
) -> None:
    if metrics.depth > policy.max_depth:
        raise GraphQLSecurityViolation(
            code=GRAPHQL_DEPTH_LIMIT_EXCEEDED,
            message=(
                "Query GraphQL excedeu a profundidade máxima permitida "
                f"({policy.max_depth})."
            ),
            details={"depth": metrics.depth, "max_depth": policy.max_depth},
        )

    if metrics.complexity > policy.max_complexity:
        raise GraphQLSecurityViolation(
            code=GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED,
            message=(
                "Query GraphQL excedeu a complexidade máxima permitida "
                f"({policy.max_complexity})."
            ),
            details={
                "complexity": metrics.complexity,
                "max_complexity": policy.max_complexity,
            },
        )


def _contains_introspection_field(selection_set: ast.SelectionSetNode | None) -> bool:
    if selection_set is None:
        return False
    for selection in selection_set.selections:
        if isinstance(selection, ast.FieldNode):
            if selection.name.value in {"__schema", "__type"}:
                return True
            if _contains_introspection_field(selection.selection_set):
                return True
        elif isinstance(selection, ast.InlineFragmentNode):
            if _contains_introspection_field(selection.selection_set):
                return True
    return False


def _enforce_introspection_policy(
    selected_operations: list[ast.OperationDefinitionNode],
    policy: GraphQLSecurityPolicy,
) -> None:
    if policy.allow_introspection:
        return
    if any(
        _contains_introspection_field(operation.selection_set)
        for operation in selected_operations
    ):
        raise GraphQLSecurityViolation(
            code=GRAPHQL_INTROSPECTION_DISABLED,
            message="Introspecção GraphQL está desabilitada neste ambiente.",
            details={},
        )


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

    document = _parse_document(query)
    fragments, operations = _collect_fragments_and_operations(document)
    _ensure_operation_count_within_limit(operations, policy)
    selected_operations = _select_operations_to_analyze(operations, operation_name)
    _enforce_introspection_policy(selected_operations, policy)
    metrics = _calculate_metrics(
        selected_operations,
        fragments=fragments,
        variable_values=variable_values,
        max_list_multiplier=policy.max_list_multiplier,
        query=query,
    )
    _enforce_depth_and_complexity_limits(metrics, policy)
    return GraphQLQueryMetrics(
        operation_count=len(operations),
        depth=metrics.depth,
        complexity=metrics.complexity,
        query_bytes=query_bytes,
    )
