"""Admin endpoint for querying entity-level audit trail (issue #1052).

Endpoint
--------
    GET /admin/audit-trail/<entity_type>/<entity_id>
        Returns up to 100 audit events for the given entity, newest first.
        Requires a valid JWT with the ``admin`` role.

Example
-------
    GET /admin/audit-trail/transaction/550e8400-e29b-41d4-a716-446655440000
    GET /admin/audit-trail/user/550e8400-e29b-41d4-a716-446655440000
"""

from __future__ import annotations

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from app.auth import get_active_auth_context
from app.controllers.response_contract import (
    compat_error_response,
    compat_success_response,
)
from app.services.audit_event_service import (
    list_entity_audit_events,
    serialize_audit_event,
)

admin_audit_trail_bp = Blueprint("admin_audit_trail", __name__)

_ALLOWED_ENTITY_TYPES = frozenset({"transaction", "user"})


def _is_admin() -> bool:
    try:
        ctx = get_active_auth_context()
        return "admin" in ctx.roles
    except Exception:
        return False


@admin_audit_trail_bp.get("/admin/audit-trail/<entity_type>/<entity_id>")
def get_entity_audit_trail(entity_type: str, entity_id: str) -> ResponseReturnValue:
    if not _is_admin():
        return compat_error_response(
            legacy_payload={"error": "Forbidden", "code": "FORBIDDEN"},
            status_code=403,
            message="Forbidden",
            error_code="FORBIDDEN",
        )

    if entity_type not in _ALLOWED_ENTITY_TYPES:
        return compat_error_response(
            legacy_payload={
                "error": (
                    f"Unknown entity_type '{entity_type}'. "
                    f"Allowed: {sorted(_ALLOWED_ENTITY_TYPES)}"
                ),
                "code": "INVALID_ENTITY_TYPE",
            },
            status_code=400,
            message=f"Unknown entity_type '{entity_type}'",
            error_code="INVALID_ENTITY_TYPE",
        )

    try:
        limit = min(int(request.args.get("limit", 100)), 500)
    except (TypeError, ValueError):
        limit = 100

    events = list_entity_audit_events(entity_type, entity_id, limit=limit)
    return compat_success_response(
        legacy_payload={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "count": len(events),
            "events": [serialize_audit_event(e) for e in events],
        },
        status_code=200,
        message="ok",
        data={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "count": len(events),
            "events": [serialize_audit_event(e) for e in events],
        },
    )
