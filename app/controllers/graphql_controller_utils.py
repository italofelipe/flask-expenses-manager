from __future__ import annotations

from typing import Any, Callable

from graphql import GraphQLError

from app.application.errors import PublicValidationError


def graphql_error_response(
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


def parse_graphql_payload(
    raw_payload: Any,
) -> tuple[str, dict[str, Any] | None, str | None]:
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    query = payload.get("query")
    variables = payload.get("variables")
    operation_name = payload.get("operationName")

    if not isinstance(query, str) or not query.strip():
        raise PublicValidationError("Campo 'query' é obrigatório.")

    parsed_variables = variables if isinstance(variables, dict) else None
    if variables is not None and parsed_variables is None:
        raise PublicValidationError("Campo 'variables' deve ser um objeto.")

    parsed_operation_name = (
        operation_name if isinstance(operation_name, str) and operation_name else None
    )
    if operation_name is not None and parsed_operation_name is None:
        raise PublicValidationError("Campo 'operationName' deve ser uma string.")

    return query, parsed_variables, parsed_operation_name


def build_graphql_result_response(
    result: Any,
    *,
    format_error: Callable[[GraphQLError], dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    response: dict[str, Any] = {}
    if result.errors:
        response["errors"] = [format_error(err) for err in result.errors]
    if result.data is not None:
        response["data"] = result.data

    status_code = 200
    if result.errors and result.data is None:
        status_code = 400
    return response, status_code
