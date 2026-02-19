from __future__ import annotations

from typing import Any

from flask import current_app, request
from graphql import GraphQLError

from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.controllers.graphql.utils import (
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
from app.graphql.errors import PUBLIC_GRAPHQL_ERROR_CODES
from app.graphql.security import (
    GraphQLSecurityPolicy,
    GraphQLSecurityViolation,
    analyze_graphql_query,
)

from .dependencies import get_graphql_authorization_policy, get_graphql_security_policy


def _sanitize_graphql_message(message: Any) -> str:
    raw = str(message or "").strip()
    compact = " ".join(raw.split())
    if not compact:
        return "An unexpected error occurred."
    if len(compact) > 240:
        return f"{compact[:240]}..."
    return compact


def _sanitize_graphql_extensions(extensions: Any) -> dict[str, Any] | None:
    """
    Sanitize GraphQL extensions before returning them to clients.

    Why
    - Some internal errors encode infra state in extensions (e.g. "redis unreachable").
    - Returning raw extensions can leak operational details to clients.

    Policy
    - Only forward a small allowlist of fields.
    - Drop everything else.
    """

    if not isinstance(extensions, dict):
        return None

    payload: dict[str, Any] = {}
    code = extensions.get("code")
    if isinstance(code, str) and code:
        payload["code"] = code

    retry_after = extensions.get("retry_after_seconds")
    if isinstance(retry_after, int) and 0 <= retry_after <= 86400:
        payload["retry_after_seconds"] = retry_after

    return payload or None


def _is_public_graphql_error(
    err: GraphQLError,
    safe_extensions: dict[str, Any] | None,
) -> bool:
    if not safe_extensions:
        return False
    code = safe_extensions.get("code")
    return isinstance(code, str) and code in PUBLIC_GRAPHQL_ERROR_CODES


def _format_graphql_execution_error(err: GraphQLError) -> dict[str, Any]:
    is_debug = bool(
        current_app.config.get("DEBUG") or current_app.config.get("TESTING")
    )
    safe_message = _sanitize_graphql_message(err.message)
    safe_extensions = _sanitize_graphql_extensions(err.extensions)
    if not is_debug:
        if _is_public_graphql_error(err, safe_extensions):
            public_payload: dict[str, Any] = {"message": safe_message}
            if safe_extensions:
                public_payload["extensions"] = safe_extensions
            return public_payload

        # GraphQL parser/validation errors (usually without original_error)
        # should stay actionable to clients while preserving a safe code.
        if err.original_error is None:
            return {
                "message": safe_message,
                "extensions": {"code": "VALIDATION_ERROR"},
            }

        current_app.logger.exception("GraphQL internal execution error", exc_info=err)
        return {
            "message": "An unexpected error occurred.",
            "extensions": {"code": "INTERNAL_ERROR", "details": {}},
        }

    payload: dict[str, Any] = {"message": safe_message}
    if safe_extensions:
        payload["extensions"] = safe_extensions
    return payload


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


def _get_security_policy() -> GraphQLSecurityPolicy:
    return get_graphql_security_policy()


def _get_authorization_policy() -> GraphQLAuthorizationPolicy:
    return get_graphql_authorization_policy()
