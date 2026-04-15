"""Shared entry service — J13 (shared transactions)."""

from __future__ import annotations

from uuid import UUID

from app.exceptions import APIError
from app.extensions.database import db
from app.models.shared_entry import SharedEntry, SharedEntryStatus, SplitType


class SharedEntryNotFoundError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Compartilhamento não encontrado.",
            code="SHARED_ENTRY_NOT_FOUND",
            status_code=404,
        )


class SharedEntryForbiddenError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Acesso não autorizado ao compartilhamento.",
            code="SHARED_ENTRY_FORBIDDEN",
            status_code=403,
        )


class SharedEntryAlreadyDeclinedError(APIError):
    def __init__(self) -> None:
        super().__init__(
            message="Este compartilhamento já foi encerrado.",
            code="SHARED_ENTRY_ALREADY_DECLINED",
            status_code=409,
        )


class SharedEntryConcurrentEditError(APIError):
    """Raised when an update is rejected due to a version mismatch (lost update)."""

    def __init__(self) -> None:
        super().__init__(
            message=(
                "O compartilhamento foi modificado por outro usuário. "
                "Recarregue e tente novamente."
            ),
            code="CONFLICT_CONCURRENT_EDIT",
            status_code=409,
        )


# Backward-compat alias so existing call-sites don't break during migration
SharedEntryAlreadyRevokedError = SharedEntryAlreadyDeclinedError


def share_entry(
    owner_id: UUID,
    transaction_id: UUID,
    split_type: str,
) -> SharedEntry:
    """Create a new shared entry for a transaction."""
    split_type_enum = SplitType(split_type)
    entry = SharedEntry(
        owner_id=owner_id,
        transaction_id=transaction_id,
        split_type=split_type_enum,
        status=SharedEntryStatus.PENDING,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def revoke_share(shared_entry_id: UUID, owner_id: UUID) -> SharedEntry:
    """Decline/revoke a shared entry by setting its status to DECLINED."""
    entry: SharedEntry | None = db.session.get(SharedEntry, shared_entry_id)
    if entry is None:
        raise SharedEntryNotFoundError()
    if entry.owner_id != owner_id:
        raise SharedEntryForbiddenError()
    if entry.status == SharedEntryStatus.DECLINED:
        raise SharedEntryAlreadyDeclinedError()
    entry.status = SharedEntryStatus.DECLINED
    db.session.commit()
    return entry


def list_shared_by_me(owner_id: UUID) -> list[SharedEntry]:
    """Return all shared entries owned by the given user."""
    # selectinload(SharedEntry.invitations) prevents N+1: the serializer
    # iterates entry.invitations for every entry in the list.
    # selectinload is preferred over joinedload for one-to-many collections
    # to avoid row-multiplication in the result set.
    from sqlalchemy.orm import selectinload

    return list(
        SharedEntry.query.options(selectinload(SharedEntry.invitations))  # type: ignore[arg-type]
        .filter_by(owner_id=owner_id)
        .order_by(SharedEntry.created_at.desc())
        .all()
    )


def list_shared_with_me(user_id: UUID) -> list[SharedEntry]:
    """Return all active shared entries where the user is an invitee."""
    from sqlalchemy import select

    from app.models.shared_entry import Invitation, InvitationStatus

    # .scalar_subquery() is required when mixing legacy Model.query with
    # SQLAlchemy 2.x select() — without it, the compiler raises an
    # ArgumentError ("Ambiguous") that surfaces as an unhandled 500.
    subquery = (
        select(Invitation.shared_entry_id)
        .where(
            Invitation.to_user_id == user_id,
            Invitation.status == InvitationStatus.ACCEPTED,
        )
        .scalar_subquery()
    )
    from sqlalchemy.orm import selectinload

    return list(
        SharedEntry.query.options(selectinload(SharedEntry.invitations))  # type: ignore[arg-type]
        .filter(SharedEntry.id.in_(subquery))
        .order_by(SharedEntry.created_at.desc())
        .all()
    )


def update_shared_entry(
    shared_entry_id: UUID,
    owner_id: UUID,
    *,
    expected_version: int,
    split_type: str | None = None,
) -> SharedEntry:
    """Update a shared entry using optimistic locking.

    The ``expected_version`` must match the current DB value.  If it does not
    (i.e., another writer modified the row in between), the function raises
    ``SharedEntryConcurrentEditError`` (HTTP 409) rather than silently
    overwriting the competing change.

    On success, ``version`` is incremented by 1 before committing.
    """
    entry: SharedEntry | None = db.session.get(SharedEntry, shared_entry_id)
    if entry is None:
        raise SharedEntryNotFoundError()
    if entry.owner_id != owner_id:
        raise SharedEntryForbiddenError()

    updates: dict[str, object] = {"version": expected_version + 1}
    if split_type is not None:
        updates["split_type"] = SplitType(split_type)

    rows_updated = SharedEntry.query.filter_by(
        id=shared_entry_id, version=expected_version
    ).update(updates, synchronize_session=False)
    if rows_updated == 0:
        db.session.rollback()
        raise SharedEntryConcurrentEditError()

    db.session.commit()
    # Reload fresh state after the out-of-band update
    db.session.refresh(entry)
    return entry


def get_shared_entry(shared_entry_id: UUID, requesting_user_id: UUID) -> SharedEntry:
    """Get a shared entry.

    Checks that the requester is the owner or an accepted invitee.
    """
    from app.models.shared_entry import Invitation, InvitationStatus

    entry: SharedEntry | None = db.session.get(SharedEntry, shared_entry_id)
    if entry is None:
        raise SharedEntryNotFoundError()
    if entry.owner_id == requesting_user_id:
        return entry
    invitation = Invitation.query.filter_by(
        shared_entry_id=shared_entry_id,
        to_user_id=requesting_user_id,
        status=InvitationStatus.ACCEPTED,
    ).first()
    if invitation is None:
        raise SharedEntryForbiddenError()
    return entry
