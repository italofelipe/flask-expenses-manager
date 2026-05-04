from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
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


# Resolvers that make external HTTP calls (BRAPI, billing provider) are weighted
# higher so that a single expensive request consumes more of the complexity budget.
# Override via GRAPHQL_FIELD_WEIGHTS_JSON env var (JSON object, field → int).
_DEFAULT_FIELD_WEIGHTS: dict[str, int] = {
    # BRAPI market-data calls — each fetches live quotes from an external API
    "investmentValuation": 10,
    "portfolioValuation": 10,
    "portfolioValuationHistory": 8,
    # Analytics aggregates — multiple DB queries
    "dashboardOverview": 3,
    "transactionDashboard": 3,
    # Billing provider query
    "billingPlans": 5,
}


def _read_field_weights_env() -> dict[str, int]:
    raw = os.getenv("GRAPHQL_FIELD_WEIGHTS_JSON", "")
    if not raw.strip():
        return dict(_DEFAULT_FIELD_WEIGHTS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): max(1, int(v)) for k, v in parsed.items()}
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return dict(_DEFAULT_FIELD_WEIGHTS)


@dataclass
class GraphQLSecurityPolicy:
    max_query_bytes: int
    max_depth: int
    max_complexity: int
    max_operations: int
    max_list_multiplier: int
    allow_introspection: bool
    field_weights: dict[str, int] = field(
        default_factory=lambda: dict(_DEFAULT_FIELD_WEIGHTS)
    )

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
            field_weights=_read_field_weights_env(),
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
        field_weights: dict[str, int] | None = None,
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
        if field_weights is not None:
            self.field_weights = {
                str(k): max(1, int(v)) for k, v in field_weights.items()
            }
