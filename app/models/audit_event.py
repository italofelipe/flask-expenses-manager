# mypy: disable-error-code=name-defined

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.extensions.database import db


class AuditEvent(db.Model):
    __tablename__ = "audit_events"
    __table_args__ = (
        db.Index("ix_audit_events_request_id", "request_id"),
        db.Index("ix_audit_events_created_at", "created_at"),
    )

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = db.Column(db.String(64), nullable=True)
    method = db.Column(db.String(12), nullable=False)
    path = db.Column(db.String(256), nullable=False)
    status = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.String(64), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
