"""Invitation service — J13 (shared transactions)."""

from __future__ import annotations

import secrets
from datetime import timedelta
from uuid import UUID

from app.exceptions import APIError
from app.extensions.database import db
from app.models.shared_entry import Invitation, InvitationStatus, SharedEntry
from app.utils.datetime_utils import utc_now_naive


class InvitationNotFoundError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Convite não encontrado.",
            code="INVITATION_NOT_FOUND",
            status_code=404,
        )


class InvitationForbiddenError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Acesso não autorizado ao convite.",
            code="INVITATION_FORBIDDEN",
            status_code=403,
        )


class InvitationExpiredError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Este convite expirou.",
            code="INVITATION_EXPIRED",
            status_code=410,
        )


class InvitationAlreadyProcessedError(APIError):
    def __init__(self, status: InvitationStatus) -> None:
        super().__init__(
            message=f"Este convite já foi processado: {status.value}.",
            code="INVITATION_ALREADY_PROCESSED",
            status_code=409,
        )


class SharedEntryNotFoundError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Compartilhamento não encontrado.",
            code="SHARED_ENTRY_NOT_FOUND",
            status_code=404,
        )


class InvitationOwnershipError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Apenas o dono do compartilhamento pode criar convites.",
            code="INVITATION_NOT_OWNER",
            status_code=403,
        )


def create_invitation(
    inviter_id: UUID,
    shared_entry_id: UUID,
    invitee_email: str,
    split_value: float | None = None,
    share_amount: float | None = None,
    message: str | None = None,
    expires_in_hours: int = 48,
) -> Invitation:
    """Create an invitation for a shared entry."""
    shared_entry: SharedEntry | None = db.session.get(SharedEntry, shared_entry_id)
    if shared_entry is None:
        raise SharedEntryNotFoundError()
    if shared_entry.owner_id != inviter_id:
        raise InvitationOwnershipError()

    token = secrets.token_urlsafe(32)
    expires_at = utc_now_naive() + timedelta(hours=expires_in_hours)

    invitation = Invitation(
        shared_entry_id=shared_entry_id,
        from_user_id=inviter_id,
        to_user_email=invitee_email,
        split_value=split_value,
        share_amount=share_amount,
        message=message,
        status=InvitationStatus.PENDING,
        token=token,
        expires_at=expires_at,
    )
    db.session.add(invitation)
    db.session.commit()
    return invitation


def accept_invitation(token: str, accepting_user_id: UUID) -> Invitation:
    """Accept a pending invitation by token."""
    invitation: Invitation | None = Invitation.query.filter_by(token=token).first()
    if invitation is None:
        raise InvitationNotFoundError()
    if invitation.status == InvitationStatus.EXPIRED or (
        invitation.expires_at is not None and invitation.expires_at < utc_now_naive()
    ):
        if invitation.status == InvitationStatus.PENDING:
            invitation.status = InvitationStatus.EXPIRED
            db.session.commit()
        raise InvitationExpiredError()
    if invitation.status != InvitationStatus.PENDING:
        raise InvitationAlreadyProcessedError(invitation.status)

    invitation.status = InvitationStatus.ACCEPTED
    invitation.to_user_id = accepting_user_id
    invitation.responded_at = utc_now_naive()
    db.session.commit()
    return invitation


def revoke_invitation(invitation_id: UUID, inviter_id: UUID) -> Invitation:
    """Revoke a pending invitation."""
    invitation: Invitation | None = db.session.get(Invitation, invitation_id)
    if invitation is None:
        raise InvitationNotFoundError()
    if invitation.from_user_id != inviter_id:
        raise InvitationForbiddenError()
    if invitation.status != InvitationStatus.PENDING:
        raise InvitationAlreadyProcessedError(invitation.status)

    invitation.status = InvitationStatus.REVOKED
    invitation.responded_at = utc_now_naive()
    db.session.commit()
    return invitation


def list_invitations(inviter_id: UUID) -> list[Invitation]:
    """Return all invitations created by the given user."""
    return list(
        Invitation.query.filter_by(from_user_id=inviter_id)
        .order_by(Invitation.created_at.desc())
        .all()
    )
