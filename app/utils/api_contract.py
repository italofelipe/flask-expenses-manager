"""Helpers to resolve API contract version from request context."""

from __future__ import annotations

from flask import has_request_context, request

CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"


def is_v2_contract_request() -> bool:
    if not has_request_context():
        return False
    header_value = str(request.headers.get(CONTRACT_HEADER, "")).strip().lower()
    return header_value == CONTRACT_V2
