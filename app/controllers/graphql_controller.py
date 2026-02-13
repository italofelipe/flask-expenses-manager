"""GraphQL controller compatibility facade."""

from app.controllers.graphql import (
    _enforce_graphql_policies,
    _format_graphql_execution_error,
    _get_authorization_policy,
    _get_security_policy,
    execute_graphql,
    graphql_bp,
    register_graphql_security,
)
from app.graphql import schema

__all__ = [
    "graphql_bp",
    "execute_graphql",
    "register_graphql_security",
    "schema",
    "_format_graphql_execution_error",
    "_enforce_graphql_policies",
    "_get_security_policy",
    "_get_authorization_policy",
]
