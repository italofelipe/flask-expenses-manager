"""Shared entries and invitations REST resources — J13."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import shared_entries_bp


def _serialize_shared_entry(entry: Any) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "owner_id": str(entry.owner_id),
        "transaction_id": str(entry.transaction_id),
        "status": entry.status.value,
        "split_type": entry.split_type.value,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def _serialize_invitation(inv: Any) -> dict[str, Any]:
    return {
        "id": str(inv.id),
        "shared_entry_id": str(inv.shared_entry_id),
        "from_user_id": str(inv.from_user_id),
        "to_user_email": inv.to_user_email,
        "to_user_id": str(inv.to_user_id) if inv.to_user_id else None,
        "split_value": float(inv.split_value) if inv.split_value is not None else None,
        "share_amount": (
            float(inv.share_amount) if inv.share_amount is not None else None
        ),
        "message": inv.message,
        "status": inv.status.value,
        "token": inv.token,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "created_at": inv.created_at.isoformat(),
        "responded_at": inv.responded_at.isoformat() if inv.responded_at else None,
    }


# ---------------------------------------------------------------------------
# Shared entries endpoints
# ---------------------------------------------------------------------------


@shared_entries_bp.route("", methods=["POST"])
@jwt_required()
def create_shared_entry() -> tuple[dict[str, Any], int]:
    """Share a transaction entry."""
    from app.services.shared_entry_service import (
        SharedEntryForbiddenError,
        SharedEntryNotFoundError,
        share_entry,
    )

    user_id: UUID = current_user_id()
    payload = request.get_json() or {}
    transaction_id_raw = payload.get("transaction_id")
    split_type = payload.get("split_type")
    if not transaction_id_raw or not split_type:
        return {"error": "transaction_id e split_type são obrigatórios."}, 400
    try:
        transaction_id = UUID(str(transaction_id_raw))
    except (ValueError, AttributeError):
        return {"error": "transaction_id inválido."}, 400

    try:
        entry = share_entry(
            owner_id=user_id,
            transaction_id=transaction_id,
            split_type=split_type,
        )
    except (SharedEntryNotFoundError, SharedEntryForbiddenError) as exc:
        return {"error": exc.message}, exc.status_code

    return {"shared_entry": _serialize_shared_entry(entry)}, 201


@shared_entries_bp.route("/by-me", methods=["GET"])
@jwt_required()
def list_shared_by_me() -> tuple[dict[str, Any], int]:
    """List all shared entries I own."""
    from app.services.shared_entry_service import list_shared_by_me as _list

    user_id: UUID = current_user_id()
    entries = _list(owner_id=user_id)
    return {"shared_entries": [_serialize_shared_entry(e) for e in entries]}, 200


@shared_entries_bp.route("/with-me", methods=["GET"])
@jwt_required()
def list_shared_with_me() -> tuple[dict[str, Any], int]:
    """List all shared entries where I am an accepted invitee."""
    from app.services.shared_entry_service import list_shared_with_me as _list

    user_id: UUID = current_user_id()
    entries = _list(user_id=user_id)
    return {"shared_entries": [_serialize_shared_entry(e) for e in entries]}, 200


@shared_entries_bp.route("/<uuid:shared_entry_id>", methods=["DELETE"])
@jwt_required()
def revoke_shared_entry(shared_entry_id: UUID) -> tuple[dict[str, Any], int]:
    """Revoke a shared entry."""
    from app.services.shared_entry_service import (
        SharedEntryAlreadyRevokedError,
        SharedEntryForbiddenError,
        SharedEntryNotFoundError,
        revoke_share,
    )

    user_id: UUID = current_user_id()
    try:
        entry = revoke_share(shared_entry_id=shared_entry_id, owner_id=user_id)
    except SharedEntryNotFoundError as exc:
        return {"error": exc.message}, exc.status_code
    except SharedEntryForbiddenError as exc:
        return {"error": exc.message}, exc.status_code
    except SharedEntryAlreadyRevokedError as exc:
        return {"error": exc.message}, exc.status_code

    return {"shared_entry": _serialize_shared_entry(entry)}, 200


# ---------------------------------------------------------------------------
# Invitation endpoints
# ---------------------------------------------------------------------------


@shared_entries_bp.route("/invitations", methods=["GET"])
@jwt_required()
def list_invitations() -> tuple[dict[str, Any], int]:
    """List all invitations I created."""
    from app.services.invitation_service import list_invitations as _list

    user_id: UUID = current_user_id()
    invitations = _list(inviter_id=user_id)
    return {"invitations": [_serialize_invitation(i) for i in invitations]}, 200


@shared_entries_bp.route("/invitations", methods=["POST"])
@jwt_required()
def create_invitation() -> tuple[dict[str, Any], int]:
    """Create an invitation for a shared entry."""
    from app.services.invitation_service import (
        InvitationOwnershipError,
        SharedEntryNotFoundError,
    )
    from app.services.invitation_service import (
        create_invitation as _create,
    )

    user_id: UUID = current_user_id()
    payload = request.get_json() or {}
    shared_entry_id_raw = payload.get("shared_entry_id")
    invitee_email = payload.get("invitee_email")
    if not shared_entry_id_raw or not invitee_email:
        return {"error": "shared_entry_id e invitee_email são obrigatórios."}, 400
    try:
        shared_entry_id = UUID(str(shared_entry_id_raw))
    except (ValueError, AttributeError):
        return {"error": "shared_entry_id inválido."}, 400

    try:
        invitation = _create(
            inviter_id=user_id,
            shared_entry_id=shared_entry_id,
            invitee_email=invitee_email,
            split_value=payload.get("split_value"),
            share_amount=payload.get("share_amount"),
            message=payload.get("message"),
            expires_in_hours=int(payload.get("expires_in_hours", 48)),
        )
    except (SharedEntryNotFoundError, InvitationOwnershipError) as exc:
        return {"error": exc.message}, exc.status_code

    return {"invitation": _serialize_invitation(invitation)}, 201


@shared_entries_bp.route("/invitations/<string:token>/accept", methods=["POST"])
@jwt_required()
def accept_invitation(token: str) -> tuple[dict[str, Any], int]:
    """Accept an invitation by its token."""
    from app.services.invitation_service import (
        InvitationAlreadyProcessedError,
        InvitationExpiredError,
        InvitationNotFoundError,
    )
    from app.services.invitation_service import (
        accept_invitation as _accept,
    )

    user_id: UUID = current_user_id()
    try:
        invitation = _accept(token=token, accepting_user_id=user_id)
    except InvitationExpiredError as exc:
        return {"error": exc.message}, exc.status_code
    except InvitationNotFoundError as exc:
        return {"error": exc.message}, exc.status_code
    except InvitationAlreadyProcessedError as exc:
        return {"error": exc.message}, exc.status_code

    return {"invitation": _serialize_invitation(invitation)}, 200


@shared_entries_bp.route("/invitations/<uuid:invitation_id>", methods=["DELETE"])
@jwt_required()
def revoke_invitation(invitation_id: UUID) -> tuple[dict[str, Any], int]:
    """Revoke a pending invitation."""
    from app.services.invitation_service import (
        InvitationAlreadyProcessedError,
        InvitationForbiddenError,
        InvitationNotFoundError,
    )
    from app.services.invitation_service import (
        revoke_invitation as _revoke,
    )

    user_id: UUID = current_user_id()
    try:
        invitation = _revoke(invitation_id=invitation_id, inviter_id=user_id)
    except InvitationNotFoundError as exc:
        return {"error": exc.message}, exc.status_code
    except InvitationForbiddenError as exc:
        return {"error": exc.message}, exc.status_code
    except InvitationAlreadyProcessedError as exc:
        return {"error": exc.message}, exc.status_code

    return {"invitation": _serialize_invitation(invitation)}, 200
