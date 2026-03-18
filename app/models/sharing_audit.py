# mypy: disable-error-code="name-defined"
"""SharingAuditEvent model — J13 domain-level audit trail for sharing actions."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class SharingAuditEvent(db.Model):
    """Domain-level audit log for sharing and invitation actions."""

    __tablename__ = "sharing_audit_events"
    __table_args__ = (
        db.Index("ix_sharing_audit_events_user_id", "user_id"),
        db.Index("ix_sharing_audit_events_resource", "resource_type", "resource_id"),
        db.Index("ix_sharing_audit_events_created_at", "created_at"),
    )

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    resource_type = db.Column(db.String(64), nullable=False)
    resource_id = db.Column(UUID(as_uuid=True), nullable=False)
    event_metadata = db.Column(JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)

    def __repr__(self) -> str:
        return (
            f"<SharingAuditEvent user={self.user_id} action={self.action} "
            f"resource={self.resource_type}/{self.resource_id}>"
        )
