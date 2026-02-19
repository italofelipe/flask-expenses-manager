from __future__ import annotations

from .blueprint import graphql_bp
from .resources import execute_graphql

_ROUTES_REGISTERED = False


def register_graphql_routes() -> None:
    """Register GraphQL HTTP routes once to avoid duplicate endpoint binding."""

    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    graphql_bp.add_url_rule("", view_func=execute_graphql, methods=["POST"])
    _ROUTES_REGISTERED = True


register_graphql_routes()
