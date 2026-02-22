from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from graphql import parse
from graphql.language import ast

from app.graphql.auth import get_current_user_optional

GRAPHQL_AUTH_REQUIRED = "GRAPHQL_AUTH_REQUIRED"
GRAPHQL_AUTH_PARSE_ERROR = "GRAPHQL_AUTH_PARSE_ERROR"


@dataclass(frozen=True)
class GraphQLAuthorizationViolation(Exception):
    code: str
    message: str
    details: dict[str, Any]


@dataclass
class GraphQLAuthorizationPolicy:
    public_queries: set[str]
    public_mutations: set[str]
    allow_unnamed_operations: bool

    @classmethod
    def from_env(cls) -> "GraphQLAuthorizationPolicy":
        return cls(
            public_queries=_read_csv_set("GRAPHQL_PUBLIC_QUERIES", "__typename"),
            public_mutations=_read_csv_set(
                "GRAPHQL_PUBLIC_MUTATIONS",
                "registerUser,login,forgotPassword,resetPassword",
            ),
            allow_unnamed_operations=_read_bool_env(
                "GRAPHQL_ALLOW_UNNAMED_OPERATIONS",
                True,
            ),
        )


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_csv_set(name: str, default: str) -> set[str]:
    raw = os.getenv(name, default)
    values = [item.strip() for item in raw.split(",")]
    return {item for item in values if item}


def _collect_operations(
    document: ast.DocumentNode,
) -> list[ast.OperationDefinitionNode]:
    operations: list[ast.OperationDefinitionNode] = []
    for definition in document.definitions:
        if isinstance(definition, ast.OperationDefinitionNode):
            operations.append(definition)
    return operations


def _select_operations(
    operations: list[ast.OperationDefinitionNode],
    operation_name: str | None,
    *,
    allow_unnamed_operations: bool,
) -> list[ast.OperationDefinitionNode]:
    if operation_name is None:
        if not allow_unnamed_operations and len(operations) != 1:
            raise GraphQLAuthorizationViolation(
                code=GRAPHQL_AUTH_PARSE_ERROR,
                message="operationName é obrigatório para múltiplas operações.",
                details={},
            )
        return operations

    selected = [
        operation
        for operation in operations
        if operation.name and operation.name.value == operation_name
    ]
    if selected:
        return selected
    raise GraphQLAuthorizationViolation(
        code=GRAPHQL_AUTH_PARSE_ERROR,
        message=f"Operação '{operation_name}' não encontrada.",
        details={},
    )


def _root_field_names(operation: ast.OperationDefinitionNode) -> set[str]:
    names: set[str] = set()
    for selection in operation.selection_set.selections:
        if isinstance(selection, ast.FieldNode):
            names.add(selection.name.value)
    return names


def _is_operation_public(
    operation: ast.OperationDefinitionNode,
    policy: GraphQLAuthorizationPolicy,
) -> bool:
    operation_fields = _root_field_names(operation)
    if operation.operation == ast.OperationType.QUERY:
        return operation_fields.issubset(policy.public_queries)
    if operation.operation == ast.OperationType.MUTATION:
        return operation_fields.issubset(policy.public_mutations)
    return False


def enforce_graphql_authorization(
    *,
    query: str,
    operation_name: str | None,
    policy: GraphQLAuthorizationPolicy,
) -> None:
    try:
        document = parse(query)
    except (
        Exception
    ) as exc:  # pragma: no cover - parse errors handled by security layer
        raise GraphQLAuthorizationViolation(
            code=GRAPHQL_AUTH_PARSE_ERROR,
            message="Query GraphQL inválida.",
            details={},
        ) from exc

    operations = _collect_operations(document)
    selected_operations = _select_operations(
        operations,
        operation_name,
        allow_unnamed_operations=policy.allow_unnamed_operations,
    )

    has_private_operation = any(
        not _is_operation_public(operation, policy) for operation in selected_operations
    )
    if not has_private_operation:
        return

    if get_current_user_optional() is None:
        raise GraphQLAuthorizationViolation(
            code=GRAPHQL_AUTH_REQUIRED,
            message="Autenticação obrigatória para esta operação GraphQL.",
            details={},
        )
