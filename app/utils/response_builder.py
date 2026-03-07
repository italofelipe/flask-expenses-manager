import os
from typing import Any, Dict, Optional

from flask import Response, current_app, has_app_context, jsonify

from app.http.error_contract import ErrorContract, serialize_error_contract

SENSITIVE_DATA_FIELDS = {
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "jwt_secret_key",
}


def _is_debug_or_testing() -> bool:
    if has_app_context():
        return bool(
            current_app.config.get("DEBUG") or current_app.config.get("TESTING")
        )
    return os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            if str(key).strip().lower() in SENSITIVE_DATA_FIELDS:
                continue
            sanitized[key] = _sanitize_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def success_payload(
    message: str,
    data: Any = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": True,
        "message": message,
        "data": _sanitize_value(data),
    }
    if meta is not None:
        payload["meta"] = _sanitize_value(meta)
    return payload


def error_payload(
    message: str,
    code: str,
    details: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = serialize_error_contract(
        ErrorContract(
            message=message,
            code=code,
            status_code=0,
            details=details,
            request_id=(
                (details or {}).get("request_id") if isinstance(details, dict) else None
            ),
        ),
        debug_or_testing=_is_debug_or_testing(),
        sensitive_fields=SENSITIVE_DATA_FIELDS,
    )
    if meta is not None:
        payload["meta"] = _sanitize_value(meta)
    return payload


def json_response(payload: Dict[str, Any], status_code: int) -> Response:
    response = jsonify(payload)
    response.status_code = status_code
    return response
