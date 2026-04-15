# mypy: disable-error-code="name-defined"
"""SharedEntry and Invitation models — J13 (shared transactions)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [str(item.value) for item in enum_cls]


class SharedEntryStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class SplitType(enum.Enum):
    EQUAL = "equal"
    PERCENTAGE = "percentage"
    CUSTOM = "custom"


class InvitationStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SharedEntry(db.Model):
    """A transaction shared between two or more users."""

    __tablename__ = "shared_entries"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    owner_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    transaction_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("transactions.id"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        db.Enum(SharedEntryStatus, values_callable=_enum_values),
        nullable=False,
        default=SharedEntryStatus.PENDING,
    )
    split_type = db.Column(
        db.Enum(SplitType, values_callable=_enum_values), nullable=False
    )
    # Optimistic locking — incremented on every write; clients must echo it back
    version = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default=db.text("0"),
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )

    transaction = db.relationship("Transaction", lazy="joined")
    invitations = db.relationship(
        "Invitation", back_populates="shared_entry", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SharedEntry id={self.id} owner={self.owner_id}>"


class Invitation(db.Model):
    """Sharing invitation sent by the owner of a SharedEntry."""

    __tablename__ = "invitations"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    shared_entry_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("shared_entries.id"),
        nullable=False,
        index=True,
    )
    from_user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True
    )
    to_user_email = db.Column(db.String(254), nullable=False)
    to_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True)
    split_value = db.Column(db.Numeric(5, 2), nullable=True)
    share_amount = db.Column(db.Numeric(12, 2), nullable=True)
    message = db.Column(db.String(300), nullable=True)
    status = db.Column(
        db.Enum(InvitationStatus, values_callable=_enum_values),
        nullable=False,
        default=InvitationStatus.PENDING,
    )
    token = db.Column(db.String(64), nullable=True, unique=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    responded_at = db.Column(db.DateTime, nullable=True)

    shared_entry = db.relationship("SharedEntry", back_populates="invitations")

    __table_args__ = (
        db.UniqueConstraint(
            "shared_entry_id",
            "to_user_email",
            name="uq_invitations_shared_entry_email",
        ),
        db.Index("ix_invitations_email_status", "to_user_email", "status"),
    )

    def __repr__(self) -> str:
        return f"<Invitation to={self.to_user_email} status={self.status}>"
