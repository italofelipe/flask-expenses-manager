from typing import Any, Dict, Optional

from flask import Response, jsonify


def success_payload(
    message: str,
    data: Any = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": True,
        "message": message,
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    return payload


def error_payload(
    message: str,
    code: str,
    details: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": False,
        "message": message,
        "error": {
            "code": code,
            "details": details or {},
        },
    }
    if meta is not None:
        payload["meta"] = meta
    return payload


def json_response(payload: Dict[str, Any], status_code: int) -> Response:
    response = jsonify(payload)
    response.status_code = status_code
    return response
