"""Sharing audit service — J13 (shared transactions).

Provides domain-level audit logging for sharing and invitation actions,
separate from the HTTP-level AuditEvent trail.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.extensions.database import db
from app.models.sharing_audit import SharingAuditEvent


def log_event(
    user_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> SharingAuditEvent:
    """Record a domain-level audit event for sharing actions."""
    event = SharingAuditEvent(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=metadata or {},
    )
    db.session.add(event)
    db.session.commit()
    return event


def get_user_audit_log(user_id: UUID, limit: int = 50) -> list[SharingAuditEvent]:
    """Return the most recent audit events for a given user."""
    safe_limit = max(1, min(int(limit), 500))
    return list(
        SharingAuditEvent.query.filter_by(user_id=user_id)
        .order_by(SharingAuditEvent.created_at.desc())
        .limit(safe_limit)
        .all()
    )
