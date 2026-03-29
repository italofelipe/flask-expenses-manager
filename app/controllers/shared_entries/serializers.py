from __future__ import annotations

from typing import TypedDict

from app.models.shared_entry import Invitation, SharedEntry


class SharedEntryPayload(TypedDict):
    id: str
    owner_id: str
    transaction_id: str
    status: str
    split_type: str
    created_at: str
    updated_at: str


class InvitationPayload(TypedDict):
    id: str
    shared_entry_id: str
    from_user_id: str
    to_user_email: str
    to_user_id: str | None
    split_value: float | None
    share_amount: float | None
    message: str | None
    status: str
    token: str | None
    expires_at: str | None
    created_at: str
    responded_at: str | None


def serialize_shared_entry(entry: SharedEntry) -> SharedEntryPayload:
    return {
        "id": str(entry.id),
        "owner_id": str(entry.owner_id),
        "transaction_id": str(entry.transaction_id),
        "status": entry.status.value,
        "split_type": entry.split_type.value,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def serialize_invitation(invitation: Invitation) -> InvitationPayload:
    return {
        "id": str(invitation.id),
        "shared_entry_id": str(invitation.shared_entry_id),
        "from_user_id": str(invitation.from_user_id),
        "to_user_email": invitation.to_user_email,
        "to_user_id": (
            str(invitation.to_user_id) if invitation.to_user_id is not None else None
        ),
        "split_value": (
            float(invitation.split_value)
            if invitation.split_value is not None
            else None
        ),
        "share_amount": (
            float(invitation.share_amount)
            if invitation.share_amount is not None
            else None
        ),
        "message": invitation.message,
        "status": invitation.status.value,
        "token": invitation.token,
        "expires_at": (
            invitation.expires_at.isoformat() if invitation.expires_at else None
        ),
        "created_at": invitation.created_at.isoformat(),
        "responded_at": (
            invitation.responded_at.isoformat() if invitation.responded_at else None
        ),
    }
