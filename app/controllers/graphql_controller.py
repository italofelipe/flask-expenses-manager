"""GraphQL controller compatibility facade."""

from app.controllers.graphql import (
    GraphQLDependencies,
    _enforce_graphql_policies,
    _format_graphql_execution_error,
    _get_authorization_policy,
    _get_security_policy,
    execute_graphql,
    get_graphql_authorization_policy,
    get_graphql_dependencies,
    get_graphql_security_policy,
    graphql_bp,
    register_graphql_dependencies,
    register_graphql_security,
)
from app.graphql import schema

__all__ = [
    "graphql_bp",
    "GraphQLDependencies",
    "register_graphql_dependencies",
    "get_graphql_dependencies",
    "get_graphql_security_policy",
    "get_graphql_authorization_policy",
    "execute_graphql",
    "register_graphql_security",
    "schema",
    "_format_graphql_execution_error",
    "_enforce_graphql_policies",
    "_get_security_policy",
    "_get_authorization_policy",
]
