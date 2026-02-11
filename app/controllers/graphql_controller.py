from typing import Any, Dict

from flask import Blueprint, Flask, current_app, request
from graphql import GraphQLError

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


def _graphql_error_response(
    *,
    message: str,
    code: str | None = None,
    details: dict[str, Any] | None = None,
    status_code: int = 400,
) -> tuple[dict[str, Any], int]:
    error: dict[str, Any] = {"message": message}
    if code is not None:
        error["extensions"] = {"code": code, "details": details or {}}
    return {"errors": [error]}, status_code


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


def _parse_graphql_payload() -> tuple[str, dict[str, Any] | None, str | None] | None:
    raw_payload = request.get_json(silent=True)
    payload: Dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    query = payload.get("query")
    variables = payload.get("variables")
    operation_name = payload.get("operationName")

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Campo 'query' é obrigatório.")

    parsed_variables = variables if isinstance(variables, dict) else None
    if variables is not None and parsed_variables is None:
        raise ValueError("Campo 'variables' deve ser um objeto.")

    parsed_operation_name = (
        operation_name if isinstance(operation_name, str) and operation_name else None
    )
    if operation_name is not None and parsed_operation_name is None:
        raise ValueError("Campo 'operationName' deve ser uma string.")

    return query, parsed_variables, parsed_operation_name


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
        return _graphql_error_response(
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
        return _graphql_error_response(
            message=exc.message,
            code=exc.code,
            details=exc.details,
            status_code=401,
        )

    return None


def _build_graphql_result_response(result: Any) -> tuple[dict[str, Any], int]:
    response: Dict[str, Any] = {}
    if result.errors:
        response["errors"] = [
            _format_graphql_execution_error(err) for err in result.errors
        ]
    if result.data is not None:
        response["data"] = result.data

    status_code = 200
    if result.errors and result.data is None:
        status_code = 400
    return response, status_code


@graphql_bp.route("", methods=["POST"])
def execute_graphql() -> tuple[dict[str, Any], int]:
    try:
        parsed_payload = _parse_graphql_payload()
    except ValueError as exc:
        return _graphql_error_response(message=str(exc), status_code=400)

    if parsed_payload is None:
        return _graphql_error_response(
            message="Campo 'query' é obrigatório.",
            status_code=400,
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
    return _build_graphql_result_response(result)


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
