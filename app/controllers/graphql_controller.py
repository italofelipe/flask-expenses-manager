from typing import Any, Dict

from flask import Blueprint, Flask, current_app, request

from app.graphql import schema
from app.graphql.security import (
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
    analyze_graphql_query,
)

graphql_bp = Blueprint("graphql", __name__, url_prefix="/graphql")


@graphql_bp.route("", methods=["POST"])  # type: ignore[misc]
def execute_graphql() -> tuple[dict[str, Any], int]:
    raw_payload = request.get_json(silent=True)
    payload: Dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    query = payload.get("query")
    variables = payload.get("variables")
    operation_name = payload.get("operationName")

    if not isinstance(query, str) or not query.strip():
        return {"errors": [{"message": "Campo 'query' é obrigatório."}]}, 400

    parsed_variables = variables if isinstance(variables, dict) else None
    if variables is not None and parsed_variables is None:
        return {"errors": [{"message": "Campo 'variables' deve ser um objeto."}]}, 400

    parsed_operation_name = (
        operation_name if isinstance(operation_name, str) and operation_name else None
    )
    if operation_name is not None and parsed_operation_name is None:
        return {
            "errors": [{"message": "Campo 'operationName' deve ser uma string."}]
        }, 400

    security_policy = _get_security_policy()
    try:
        analyze_graphql_query(
            query=query,
            operation_name=parsed_operation_name,
            variable_values=parsed_variables,
            policy=security_policy,
        )
    except GraphQLSecurityViolation as exc:
        return (
            {
                "errors": [
                    {
                        "message": exc.message,
                        "extensions": {
                            "code": exc.code,
                            "details": exc.details,
                        },
                    }
                ]
            },
            400,
        )

    result = schema.execute(
        query,
        variable_values=parsed_variables,
        operation_name=parsed_operation_name,
        context_value={"request": request},
    )

    response: Dict[str, Any] = {}
    if result.errors:
        response["errors"] = [{"message": err.message} for err in result.errors]
    if result.data is not None:
        response["data"] = result.data

    status_code = 200
    if result.errors and result.data is None:
        status_code = 400
    return response, status_code


def register_graphql_security(app: Flask) -> None:
    app.extensions["graphql_security_policy"] = GraphQLSecurityPolicy.from_env()


def _get_security_policy() -> GraphQLSecurityPolicy:
    policy = current_app.extensions.get("graphql_security_policy")
    if isinstance(policy, GraphQLSecurityPolicy):
        return policy

    fallback = GraphQLSecurityPolicy.from_env()
    current_app.extensions["graphql_security_policy"] = fallback
    return fallback
