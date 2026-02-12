from __future__ import annotations

from typing import Any

from flask import Response, has_request_context, jsonify, request

from app.utils.response_builder import error_payload, success_payload

JSON_MIMETYPE = "application/json"
CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"


def is_v2_contract() -> bool:
    if not has_request_context():
        return False
    header_value = str(request.headers.get(CONTRACT_HEADER, "")).strip().lower()
    return header_value == CONTRACT_V2


def compat_success(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    data: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> Response:
    payload = legacy_payload
    if is_v2_contract():
        payload = success_payload(message=message, data=data, meta=meta)
    return Response(
        jsonify(payload).get_data(),
        status=status_code,
        mimetype=JSON_MIMETYPE,
    )


def compat_error(
    *,
    legacy_payload: dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: dict[str, Any] | None = None,
) -> Response:
    payload = legacy_payload
    if is_v2_contract():
        payload = error_payload(message=message, code=error_code, details=details)
    return Response(
        jsonify(payload).get_data(),
        status=status_code,
        mimetype=JSON_MIMETYPE,
    )
