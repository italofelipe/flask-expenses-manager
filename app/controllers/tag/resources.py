"""Tag controller resources — CRUD endpoints for user tags."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.extensions.database import db
from app.models.tag import Tag
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import tag_bp


@tag_bp.route("", methods=["GET"])
@jwt_required()
def list_tags() -> tuple[dict[str, Any], int]:
    """List all tags belonging to the authenticated user."""
    user_id = current_user_id()
    tags = Tag.query.filter_by(user_id=user_id).order_by(Tag.name).all()
    data = {
        "tags": [{"id": str(t.id), "name": t.name} for t in tags],
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
            legacy_payload={"error": "Field 'name' is required"},
            status_code=400,
            message="Field 'name' is required",
            error_code="MISSING_NAME",
        )
    if len(name) > 50:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'name' must be at most 50 characters"},
            status_code=400,
            message="Field 'name' must be at most 50 characters",
            error_code="NAME_TOO_LONG",
        )

    tag = Tag(user_id=user_id, name=name)
    db.session.add(tag)
    db.session.commit()

    tag_data = {"id": str(tag.id), "name": tag.name}
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
            legacy_payload={"error": "Tag not found"},
            status_code=404,
            message="Tag not found",
            error_code="NOT_FOUND",
        )

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'name' is required"},
            status_code=400,
            message="Field 'name' is required",
            error_code="MISSING_NAME",
        )
    if len(name) > 50:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'name' must be at most 50 characters"},
            status_code=400,
            message="Field 'name' must be at most 50 characters",
            error_code="NAME_TOO_LONG",
        )

    tag.name = name
    db.session.commit()

    tag_data = {"id": str(tag.id), "name": tag.name}
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
            legacy_payload={"error": "Tag not found"},
            status_code=404,
            message="Tag not found",
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
