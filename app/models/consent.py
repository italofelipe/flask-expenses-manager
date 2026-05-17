# mypy: disable-error-code="name-defined,no-redef"
"""Consent model — LGPD versioned acceptance/revocation tracking.

Each row is one acceptance OR revocation event of a specific consent kind
at a specific version. The latest event per ``(user, kind)`` determines the
current status. The table is append-only — events are never overwritten so
LGPD auditors can reconstruct the full history of grants and revocations.

Issue: #1259
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class ConsentKind(str, enum.Enum):
    """LGPD-relevant consent categories tracked in MVP2."""

    TERMS = "terms"
    PRIVACY = "privacy"
    COOKIES = "cookies"
    AI = "ai"
    MARKETING = "marketing"


class ConsentAction(str, enum.Enum):
    """Direction of the consent event — grant or revoke."""

    GRANTED = "granted"
    REVOKED = "revoked"


class ConsentSource(str, enum.Enum):
    """How the consent event reached the API. Minimised — no IP, no UA."""

    WEB = "web"
    APP = "app"
    API = "api"
    SYSTEM = "system"


class Consent(db.Model):
    """Append-only audit log of consent acceptance/revocation events."""

    __tablename__ = "consents"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # native_enum=False keeps the column as VARCHAR + CHECK constraint, which
    # avoids the SQLAlchemy "CREATE TYPE before migration" trap. See the
    # migration conventions in CLAUDE.md.
    kind = db.Column(
        db.Enum(ConsentKind, name="consent_kind", native_enum=False),
        nullable=False,
    )
    version = db.Column(db.String(32), nullable=False)
    action = db.Column(
        db.Enum(ConsentAction, name="consent_action", native_enum=False),
        nullable=False,
    )
    source = db.Column(
        db.Enum(ConsentSource, name="consent_source", native_enum=False),
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now_naive,
        index=True,
    )

    __table_args__ = (db.Index("ix_consents_user_kind", "user_id", "kind"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Consent id={self.id} user_id={self.user_id} kind={self.kind} "
            f"version={self.version} action={self.action}>"
        )
