"""Admin endpoints for backend-only AI Insight audit preview."""

from __future__ import annotations

import uuid
from datetime import date

from flask import Blueprint, Response, request

from app.auth import get_active_auth_context
from app.controllers.response_contract import (
    compat_error_response,
    compat_success_response,
)
from app.services.ai_insight_audit import build_ai_insight_preview

admin_ai_insights_bp = Blueprint("admin_ai_insights", __name__)


def _is_admin() -> bool:
    try:
        ctx = get_active_auth_context()
        return "admin" in ctx.roles
    except Exception:
        return False


def _forbidden_response() -> Response:
    return compat_error_response(
        legacy_payload={
            "message": "Forbidden",
            "success": False,
            "error": {"code": "FORBIDDEN", "details": {}},
        },
        status_code=403,
        message="Forbidden",
        error_code="FORBIDDEN",
    )


def _validation_response(message: str) -> Response:
    return compat_error_response(
        legacy_payload={"error": message},
        status_code=400,
        message=message,
        error_code="VALIDATION_ERROR",
    )


def _parse_preview_body() -> (
    tuple[Response, None, None, None]
    | tuple[
        None,
        uuid.UUID,
        str,
        date | None,
    ]
):
    body = request.get_json(silent=True) or {}

    try:
        user_id = uuid.UUID(str(body.get("user_id", "")))
    except (TypeError, ValueError):
        return _validation_response("user_id deve ser um UUID válido"), None, None, None

    period_type = str(body.get("period_type", "")).strip().lower()
    if period_type not in {"daily", "weekly", "monthly"}:
        return (
            _validation_response("period_type deve ser daily, weekly ou monthly"),
            None,
            None,
            None,
        )

    raw_anchor_date = body.get("anchor_date")
    if raw_anchor_date in (None, ""):
        return None, user_id, period_type, None
    try:
        anchor_date = date.fromisoformat(str(raw_anchor_date))
    except ValueError:
        return (
            _validation_response("anchor_date deve estar no formato YYYY-MM-DD"),
            None,
            None,
            None,
        )
    return None, user_id, period_type, anchor_date


@admin_ai_insights_bp.post("/ai-insights/preview")
def create_ai_insight_preview() -> Response:
    """Create a deterministic AI Insight preview without calling GPT."""

    if not _is_admin():
        return _forbidden_response()

    error, user_id, period_type, anchor_date = _parse_preview_body()
    if error is not None:
        return error
    assert user_id is not None
    assert period_type is not None

    try:
        payload = build_ai_insight_preview(
            user_id=user_id,
            period_type=period_type,
            anchor_date=anchor_date,
        )
    except ValueError as exc:
        return _validation_response(str(exc))

    return compat_success_response(
        legacy_payload=payload,
        status_code=201,
        message="Preview de AI Insight criado com sucesso",
        data=payload,
    )


__all__ = ["admin_ai_insights_bp"]
