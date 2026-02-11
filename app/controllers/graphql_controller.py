from typing import Any

from flask import Blueprint, Flask, current_app, request
from graphql import GraphQLError

from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.controllers.graphql_controller_utils import (
    build_graphql_result_response,
    graphql_error_response,
    parse_graphql_payload,
)
from app.graphql import schema
from app.graphql.authorization import (
    GraphQLAuthorizationPolicy,
    GraphQLAuthorizationViolation,
    enforce_graphql_authorization,
)
from app.graphql.security import (
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
    analyze_graphql_query,
)

graphql_bp = Blueprint("graphql", __name__, url_prefix="/graphql")


def _format_graphql_execution_error(err: GraphQLError) -> dict[str, Any]:
    is_debug = bool(
        current_app.config.get("DEBUG") or current_app.config.get("TESTING")
    )
    if err.original_error is not None and not is_debug:
        current_app.logger.exception("GraphQL internal execution error", exc_info=err)
        return {
            "message": "An unexpected error occurred.",
            "extensions": {"code": "INTERNAL_ERROR", "details": {}},
        }
    return {"message": err.message}


def _enforce_graphql_policies(
    *,
    query: str,
    parsed_variables: dict[str, Any] | None,
    parsed_operation_name: str | None,
) -> tuple[dict[str, Any], int] | None:
    security_policy = _get_security_policy()
    try:
        analyze_graphql_query(
            query=query,
            operation_name=parsed_operation_name,
            variable_values=parsed_variables,
            policy=security_policy,
        )
    except GraphQLSecurityViolation as exc:
        return graphql_error_response(
            message=exc.message,
            code=exc.code,
            details=exc.details,
            status_code=400,
        )

    authorization_policy = _get_authorization_policy()
    try:
        enforce_graphql_authorization(
            query=query,
            operation_name=parsed_operation_name,
            policy=authorization_policy,
        )
    except GraphQLAuthorizationViolation as exc:
        return graphql_error_response(
            message=exc.message,
            code=exc.code,
            details=exc.details,
            status_code=401,
        )

    return None


@graphql_bp.route("", methods=["POST"])
def execute_graphql() -> tuple[dict[str, Any], int]:
    try:
        parsed_payload = parse_graphql_payload(request.get_json(silent=True))
    except ValueError as exc:
        mapped_error = map_validation_exception(
            exc,
            fallback_message="Payload GraphQL inválido.",
        )
        return graphql_error_response(
            message=mapped_error.message,
            code=mapped_error.code,
            details=mapped_error.details,
            status_code=mapped_error.status_code,
        )
    query, parsed_variables, parsed_operation_name = parsed_payload
    policy_error = _enforce_graphql_policies(
        query=query,
        parsed_variables=parsed_variables,
        parsed_operation_name=parsed_operation_name,
    )
    if policy_error is not None:
        return policy_error

    result = schema.execute(
        query,
        variable_values=parsed_variables,
        operation_name=parsed_operation_name,
        context_value={"request": request},
    )
    return build_graphql_result_response(
        result,
        format_error=_format_graphql_execution_error,
    )


def register_graphql_security(app: Flask) -> None:
    app.extensions["graphql_security_policy"] = GraphQLSecurityPolicy.from_env()
    app.extensions["graphql_authorization_policy"] = (
        GraphQLAuthorizationPolicy.from_env()
    )


def _get_security_policy() -> GraphQLSecurityPolicy:
    policy = current_app.extensions.get("graphql_security_policy")
    if isinstance(policy, GraphQLSecurityPolicy):
        return policy

    fallback = GraphQLSecurityPolicy.from_env()
    current_app.extensions["graphql_security_policy"] = fallback
    return fallback


def _get_authorization_policy() -> GraphQLAuthorizationPolicy:
    policy = current_app.extensions.get("graphql_authorization_policy")
    if isinstance(policy, GraphQLAuthorizationPolicy):
        return policy

    fallback = GraphQLAuthorizationPolicy.from_env()
    current_app.extensions["graphql_authorization_policy"] = fallback
    return fallback
