from typing import Any, Dict

from flask import Blueprint, jsonify, request

from app.graphql import schema

graphql_bp = Blueprint("graphql", __name__, url_prefix="/graphql")


@graphql_bp.route("", methods=["POST"])  # type: ignore[misc]
def execute_graphql() -> tuple[dict[str, Any], int]:
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    query = payload.get("query")
    variables = payload.get("variables")
    operation_name = payload.get("operationName")

    if not query:
        return {"errors": [{"message": "Campo 'query' é obrigatório."}]}, 400

    result = schema.execute(
        query,
        variable_values=variables,
        operation_name=operation_name,
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
    return jsonify(response), status_code
