from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

GRAPHQL_QUERY_TOO_LARGE = "GRAPHQL_QUERY_TOO_LARGE"
GRAPHQL_DEPTH_LIMIT_EXCEEDED = "GRAPHQL_DEPTH_LIMIT_EXCEEDED"
GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED = "GRAPHQL_COMPLEXITY_LIMIT_EXCEEDED"
GRAPHQL_OPERATION_LIMIT_EXCEEDED = "GRAPHQL_OPERATION_LIMIT_EXCEEDED"
GRAPHQL_OPERATION_NOT_FOUND = "GRAPHQL_OPERATION_NOT_FOUND"
GRAPHQL_INTROSPECTION_DISABLED = "GRAPHQL_INTROSPECTION_DISABLED"


@dataclass(frozen=True)
class GraphQLSecurityViolation(Exception):
    code: str
    message: str
    details: dict[str, Any]


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
