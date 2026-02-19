from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from flask import Flask, current_app

from app.graphql.authorization import GraphQLAuthorizationPolicy
from app.graphql.security import GraphQLSecurityPolicy

GRAPHQL_DEPENDENCIES_EXTENSION_KEY = "graphql_dependencies"


@dataclass(frozen=True)
class GraphQLDependencies:
    """Container for GraphQL policy factories used by controller resources."""

    security_policy_factory: Callable[[], GraphQLSecurityPolicy]
    authorization_policy_factory: Callable[[], GraphQLAuthorizationPolicy]


def _default_dependencies() -> GraphQLDependencies:
    return GraphQLDependencies(
        security_policy_factory=GraphQLSecurityPolicy.from_env,
        authorization_policy_factory=GraphQLAuthorizationPolicy.from_env,
    )


def register_graphql_dependencies(
    app: Flask,
    dependencies: GraphQLDependencies | None = None,
) -> None:
    """Register GraphQL dependency providers and memoized policy instances."""

    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(GRAPHQL_DEPENDENCIES_EXTENSION_KEY, dependencies)
    app.extensions.setdefault(
        "graphql_security_policy", dependencies.security_policy_factory()
    )
    app.extensions.setdefault(
        "graphql_authorization_policy", dependencies.authorization_policy_factory()
    )


def get_graphql_dependencies() -> GraphQLDependencies:
    """Resolve GraphQL dependencies from app extensions with safe fallback."""

    configured = current_app.extensions.get(GRAPHQL_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, GraphQLDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[GRAPHQL_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback


def get_graphql_security_policy() -> GraphQLSecurityPolicy:
    """Return cached security policy, creating it via configured factory when needed."""

    policy = current_app.extensions.get("graphql_security_policy")
    if isinstance(policy, GraphQLSecurityPolicy):
        return policy

    dependencies = get_graphql_dependencies()
    fallback = dependencies.security_policy_factory()
    current_app.extensions["graphql_security_policy"] = fallback
    return fallback


def get_graphql_authorization_policy() -> GraphQLAuthorizationPolicy:
    """Return cached authorization policy, creating it on first access."""

    policy = current_app.extensions.get("graphql_authorization_policy")
    if isinstance(policy, GraphQLAuthorizationPolicy):
        return policy

    dependencies = get_graphql_dependencies()
    fallback = dependencies.authorization_policy_factory()
    current_app.extensions["graphql_authorization_policy"] = fallback
    return fallback


def register_graphql_security(app: Flask) -> None:
    # Backward-compatible alias used by create_app import.
    register_graphql_dependencies(app)
