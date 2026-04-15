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
        db.Index("ix_audit_events_entity", "entity_type", "entity_id"),
    )

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = db.Column(db.String(64), nullable=True)
    method = db.Column(db.String(12), nullable=False, server_default="SYSTEM")
    path = db.Column(db.String(256), nullable=False, server_default="")
    status = db.Column(db.Integer, nullable=False, server_default="0")
    user_id = db.Column(db.String(64), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    # Entity-level audit fields for soft-delete trail (#1052)
    entity_type = db.Column(db.String(64), nullable=True)
    entity_id = db.Column(db.String(64), nullable=True)
    action = db.Column(db.String(32), nullable=True)
    actor_id = db.Column(db.String(64), nullable=True)
    extra = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
