from __future__ import annotations

from graphql.language import ast

from app.graphql.complexity.policy import (
    GRAPHQL_INTROSPECTION_DISABLED,
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
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


def enforce_introspection_policy(
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
