from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from graphql import GraphQLError, parse
from graphql.language import ast

from app.graphql.complexity.policy import (
    GRAPHQL_OPERATION_LIMIT_EXCEEDED,
    GRAPHQL_OPERATION_NOT_FOUND,
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
)

_LIST_ARGUMENT_NAMES = {
    "first",
    "last",
    "limit",
    "perPage",
    "per_page",
    "pageSize",
    "size",
}


@dataclass(frozen=True)
class GraphQLQueryMetrics:
    operation_count: int
    depth: int
    complexity: int
    query_bytes: int
    root_fields: tuple[str, ...] = ()


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
        nested_depth, nested_complexity = _analyze_single_selection(
            selection,
            current_depth=current_depth,
            fragments=fragments,
            variable_values=variable_values,
            max_list_multiplier=max_list_multiplier,
            visited_fragments=visited_fragments,
        )
        max_depth = max(max_depth, nested_depth)
        complexity += nested_complexity

    return max_depth, complexity


def _analyze_single_selection(
    selection: ast.SelectionNode,
    *,
    current_depth: int,
    fragments: dict[str, ast.FragmentDefinitionNode],
    variable_values: dict[str, Any] | None,
    max_list_multiplier: int,
    visited_fragments: set[str],
) -> tuple[int, int]:
    if isinstance(selection, ast.FieldNode):
        return _analyze_field_selection(
            selection,
            current_depth=current_depth,
            fragments=fragments,
            variable_values=variable_values,
            max_list_multiplier=max_list_multiplier,
            visited_fragments=visited_fragments,
        )
    if isinstance(selection, ast.InlineFragmentNode):
        return _analyze_inline_fragment_selection(
            selection,
            current_depth=current_depth,
            fragments=fragments,
            variable_values=variable_values,
            max_list_multiplier=max_list_multiplier,
            visited_fragments=visited_fragments,
        )
    if isinstance(selection, ast.FragmentSpreadNode):
        return _analyze_fragment_spread_selection(
            selection,
            current_depth=current_depth,
            fragments=fragments,
            variable_values=variable_values,
            max_list_multiplier=max_list_multiplier,
            visited_fragments=visited_fragments,
        )
    return current_depth, 0


def _analyze_field_selection(
    selection: ast.FieldNode,
    *,
    current_depth: int,
    fragments: dict[str, ast.FragmentDefinitionNode],
    variable_values: dict[str, Any] | None,
    max_list_multiplier: int,
    visited_fragments: set[str],
) -> tuple[int, int]:
    field_depth = current_depth + 1
    field_complexity = 1
    if not selection.selection_set:
        return field_depth, field_complexity

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
    return field_depth, field_complexity


def _analyze_inline_fragment_selection(
    selection: ast.InlineFragmentNode,
    *,
    current_depth: int,
    fragments: dict[str, ast.FragmentDefinitionNode],
    variable_values: dict[str, Any] | None,
    max_list_multiplier: int,
    visited_fragments: set[str],
) -> tuple[int, int]:
    if not selection.selection_set:
        return current_depth, 0
    return _analyze_selection_set(
        selection.selection_set,
        current_depth=current_depth,
        fragments=fragments,
        variable_values=variable_values,
        max_list_multiplier=max_list_multiplier,
        visited_fragments=visited_fragments.copy(),
    )


def _analyze_fragment_spread_selection(
    selection: ast.FragmentSpreadNode,
    *,
    current_depth: int,
    fragments: dict[str, ast.FragmentDefinitionNode],
    variable_values: dict[str, Any] | None,
    max_list_multiplier: int,
    visited_fragments: set[str],
) -> tuple[int, int]:
    fragment_name = selection.name.value
    if fragment_name in visited_fragments:
        return current_depth, 0
    fragment_node = fragments.get(fragment_name)
    if fragment_node is None:
        return current_depth, 0
    next_visited = visited_fragments.copy()
    next_visited.add(fragment_name)
    return _analyze_selection_set(
        fragment_node.selection_set,
        current_depth=current_depth,
        fragments=fragments,
        variable_values=variable_values,
        max_list_multiplier=max_list_multiplier,
        visited_fragments=next_visited,
    )


def parse_document(query: str) -> ast.DocumentNode:
    try:
        return parse(query)
    except GraphQLError as exc:
        raise GraphQLSecurityViolation(
            code="GRAPHQL_PARSE_ERROR",
            message=f"Query GraphQL inválida: {exc.message}",
            details={},
        ) from exc


def collect_fragments_and_operations(
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


def ensure_operation_count_within_limit(
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


def select_operations_to_analyze(
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


def _collect_root_fields(
    operations: list[ast.OperationDefinitionNode],
) -> set[str]:
    root_fields: set[str] = set()
    for operation in operations:
        for selection in operation.selection_set.selections:
            if isinstance(selection, ast.FieldNode):
                root_fields.add(selection.name.value)
    return root_fields


def calculate_metrics(
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

    root_fields = _collect_root_fields(operations)
    return GraphQLQueryMetrics(
        operation_count=len(operations),
        depth=max_depth,
        complexity=total_complexity,
        query_bytes=len(query.encode("utf-8")),
        root_fields=tuple(sorted(root_fields)),
    )


def enforce_depth_and_complexity_limits(
    metrics: GraphQLQueryMetrics,
    policy: GraphQLSecurityPolicy,
) -> None:
    if metrics.depth > policy.max_depth:
        raise GraphQLSecurityViolation(
            code="GRAPHQL_DEPTH_LIMIT_EXCEEDED",
            message=(
                "Query GraphQL excedeu a profundidade máxima permitida "
                f"({policy.max_depth})."
            ),
            details={"depth": metrics.depth, "max_depth": policy.max_depth},
        )

    if metrics.complexity > policy.max_complexity:
        raise GraphQLSecurityViolation(
            code="GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED",
            message=(
                "Query GraphQL excedeu a complexidade máxima permitida "
                f"({policy.max_complexity})."
            ),
            details={
                "complexity": metrics.complexity,
                "max_complexity": policy.max_complexity,
            },
        )
