"""Tag controller resources — CRUD endpoints for user tags."""

from __future__ import annotations

import re

# mypy: disable-error-code=untyped-decorator
from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.extensions.database import db
from app.models.tag import Tag
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import tag_bp

MISSING_NAME_MESSAGE = "Field 'name' is required"
NAME_TOO_LONG_MESSAGE = "Field 'name' must be at most 50 characters"
TAG_NOT_FOUND_MESSAGE = "Tag not found"
INVALID_COLOR_MESSAGE = "Field 'color' must be a valid hex color code (e.g. #FF6B6B)"
# Accept #RRGGBB and #RRGGBBAA; alpha is stripped before persisting.
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


def _serialize_tag(t: Tag) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "name": t.name,
        "color": t.color,
        "icon": t.icon,
    }


def _validate_color(color: str | None) -> bool:
    if color is None:
        return True
    return bool(_HEX_COLOR_RE.match(color))


def _normalize_color(color: str | None) -> str | None:
    if color is None:
        return None
    if _HEX_COLOR_RE.match(color):
        return color[:7]
    return color


@tag_bp.route("", methods=["GET"])
@jwt_required()
def list_tags() -> tuple[dict[str, Any], int]:
    """List all tags belonging to the authenticated user."""
    user_id = current_user_id()
    tags = Tag.query.filter_by(user_id=user_id).order_by(Tag.name).all()
    data = {
        "tags": [_serialize_tag(t) for t in tags],
        "total": len(tags),
    }
    return compat_success_tuple(
        legacy_payload=data,
        status_code=200,
        message="Tags listadas com sucesso",
        data=data,
    )


@tag_bp.route("", methods=["POST"])
@jwt_required()
def create_tag() -> tuple[dict[str, Any], int]:
    """Create a new tag for the authenticated user."""
    user_id = current_user_id()
    payload = request.get_json(silent=True) or {}

    name = (payload.get("name") or "").strip()
    if not name:
        return compat_error_tuple(
            legacy_payload={"error": MISSING_NAME_MESSAGE},
            status_code=400,
            message=MISSING_NAME_MESSAGE,
            error_code="MISSING_NAME",
        )
    if len(name) > 50:
        return compat_error_tuple(
            legacy_payload={"error": NAME_TOO_LONG_MESSAGE},
            status_code=400,
            message=NAME_TOO_LONG_MESSAGE,
            error_code="NAME_TOO_LONG",
        )

    color = payload.get("color") or None
    if not _validate_color(color):
        return compat_error_tuple(
            legacy_payload={"error": INVALID_COLOR_MESSAGE},
            status_code=400,
            message=INVALID_COLOR_MESSAGE,
            error_code="INVALID_COLOR",
        )
    color = _normalize_color(color)
    icon = payload.get("icon") or None

    tag = Tag(user_id=user_id, name=name, color=color, icon=icon)
    db.session.add(tag)
    db.session.commit()

    tag_data = _serialize_tag(tag)
    return compat_success_tuple(
        legacy_payload={"message": "Tag criada com sucesso", "tag": tag_data},
        status_code=201,
        message="Tag criada com sucesso",
        data={"tag": tag_data},
    )


@tag_bp.route("/<uuid:tag_id>", methods=["PUT"])
@jwt_required()
def update_tag(tag_id: UUID) -> tuple[dict[str, Any], int]:
    """Update an existing tag belonging to the authenticated user."""
    user_id = current_user_id()
    tag = Tag.query.filter_by(id=tag_id, user_id=user_id).first()
    if tag is None:
        return compat_error_tuple(
            legacy_payload={"error": TAG_NOT_FOUND_MESSAGE},
            status_code=404,
            message=TAG_NOT_FOUND_MESSAGE,
            error_code="NOT_FOUND",
        )

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return compat_error_tuple(
            legacy_payload={"error": MISSING_NAME_MESSAGE},
            status_code=400,
            message=MISSING_NAME_MESSAGE,
            error_code="MISSING_NAME",
        )
    if len(name) > 50:
        return compat_error_tuple(
            legacy_payload={"error": NAME_TOO_LONG_MESSAGE},
            status_code=400,
            message=NAME_TOO_LONG_MESSAGE,
            error_code="NAME_TOO_LONG",
        )

    color = payload.get("color") or None
    if "color" in payload and not _validate_color(color):
        return compat_error_tuple(
            legacy_payload={"error": INVALID_COLOR_MESSAGE},
            status_code=400,
            message=INVALID_COLOR_MESSAGE,
            error_code="INVALID_COLOR",
        )

    tag.name = name
    if "color" in payload:
        tag.color = _normalize_color(color)
    if "icon" in payload:
        tag.icon = payload.get("icon") or None
    db.session.commit()

    tag_data = _serialize_tag(tag)
    return compat_success_tuple(
        legacy_payload={"message": "Tag atualizada com sucesso", "tag": tag_data},
        status_code=200,
        message="Tag atualizada com sucesso",
        data={"tag": tag_data},
    )


@tag_bp.route("/<uuid:tag_id>", methods=["DELETE"])
@jwt_required()
def delete_tag(tag_id: UUID) -> tuple[dict[str, Any], int]:
    """Delete a tag belonging to the authenticated user."""
    user_id = current_user_id()
    tag = Tag.query.filter_by(id=tag_id, user_id=user_id).first()
    if tag is None:
        return compat_error_tuple(
            legacy_payload={"error": TAG_NOT_FOUND_MESSAGE},
            status_code=404,
            message=TAG_NOT_FOUND_MESSAGE,
            error_code="NOT_FOUND",
        )

    db.session.delete(tag)
    db.session.commit()

    return compat_success_tuple(
        legacy_payload={"message": "Tag removida com sucesso"},
        status_code=200,
        message="Tag removida com sucesso",
        data={},
    )
