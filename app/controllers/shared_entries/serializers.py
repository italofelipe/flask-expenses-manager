from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TypedDict

from app.models.shared_entry import Invitation, InvitationStatus, SharedEntry, SplitType


class SharedEntryPayload(TypedDict):
    id: str
    owner_id: str
    transaction_id: str
    status: str
    split_type: str
    transaction_title: str | None
    transaction_amount: float | None
    my_share: float | None
    other_party_email: str | None
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


def _compute_my_share(
    split_type: SplitType,
    amount: Decimal,
    invitation: Invitation | None,
) -> float | None:
    """Compute the caller's share of the transaction amount.

    For *by-me* entries the invitation represents the *other party*, so
    my_share is the complement (amount - invitee_share).  For *with-me*
    entries the invitation belongs to the current user (as invitee), so
    my_share IS the invitation's share amount or split_value-derived value.

    The serializer receives the first/only invitation available on the
    SharedEntry.  Callers that need the perspective of the invitee must
    pass the relevant invitation explicitly.
    """
    if amount is None:
        return None
    if split_type == SplitType.EQUAL:
        return float(amount / Decimal("2"))
    if split_type == SplitType.PERCENTAGE:
        if invitation is not None and invitation.split_value is not None:
            return float(amount * invitation.split_value / Decimal("100"))
        return None
    if split_type == SplitType.CUSTOM:
        if invitation is not None and invitation.share_amount is not None:
            return float(invitation.share_amount)
        return None
    return None


def serialize_shared_entry(
    entry: SharedEntry,
    *,
    perspective_invitation: Invitation | None = None,
) -> SharedEntryPayload:
    """Serialize a SharedEntry with enriched transaction and share data.

    Parameters
    ----------
    entry:
        The SharedEntry ORM instance.  Its ``transaction`` relationship
        must be loaded (lazy="joined" on the model guarantees this).
    perspective_invitation:
        Pass the invitation that belongs to the *requesting user* to
        compute ``my_share`` and ``other_party_email`` from the invitee
        perspective (used by the ``with-me`` endpoint).  When ``None``,
        the first invitation on the entry is used (owner perspective).
    """
    txn = entry.transaction
    transaction_title: str | None = txn.title if txn is not None else None
    transaction_amount: float | None = (
        float(txn.amount) if txn is not None and txn.amount is not None else None
    )

    invitation: Invitation | None = perspective_invitation
    invitations_list: list[Invitation] = list(entry.invitations)
    if invitation is None and invitations_list:
        invitation = invitations_list[0]

    raw_amount: Decimal | None = (
        Decimal(str(txn.amount)) if txn is not None and txn.amount is not None else None
    )
    my_share: float | None = (
        _compute_my_share(entry.split_type, raw_amount, invitation)
        if raw_amount is not None
        else None
    )

    other_party_email: str | None = (
        invitation.to_user_email if invitation is not None else None
    )

    return {
        "id": str(entry.id),
        "owner_id": str(entry.owner_id),
        "transaction_id": str(entry.transaction_id),
        "status": entry.status.value,
        "split_type": entry.split_type.value,
        "transaction_title": transaction_title,
        "transaction_amount": transaction_amount,
        "my_share": my_share,
        "other_party_email": other_party_email,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def serialize_shared_entry_with_me(
    entry: SharedEntry,
    requesting_user_id: uuid.UUID,
) -> SharedEntryPayload:
    """Serialize a SharedEntry from the invitee's perspective.

    Finds the invitation belonging to ``requesting_user_id`` so that
    ``my_share`` and ``other_party_email`` reflect the invitee's view
    (other_party_email becomes the *owner's* email, resolved via the
    invitation's ``from_user_id``; for now we expose the invitee email
    stored on the invitation record itself — the owner created it for
    that address).
    """
    perspective: Invitation | None = None
    for inv in list(entry.invitations):
        if (
            inv.to_user_id == requesting_user_id
            and inv.status == InvitationStatus.ACCEPTED
        ):
            perspective = inv
            break
    return serialize_shared_entry(entry, perspective_invitation=perspective)


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
