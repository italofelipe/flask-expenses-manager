from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.extensions.database import db
from app.models.audit_event import AuditEvent


@dataclass(frozen=True)
class AuditSearchFilters:
    request_id: str
    limit: int = 100

    @property
    def normalized_request_id(self) -> str:
        return self.request_id.strip()

    @property
    def normalized_limit(self) -> int:
        return min(max(int(self.limit), 1), 500)


def search_audit_events_by_request_id(
    request_id: str,
    *,
    limit: int = 100,
) -> list[AuditEvent]:
    filters = AuditSearchFilters(request_id=request_id, limit=limit)
    normalized_request_id = filters.normalized_request_id
    if not normalized_request_id:
        return []

    return list(
        AuditEvent.query.filter_by(request_id=normalized_request_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(filters.normalized_limit)
        .all()
    )


def purge_expired_audit_events(*, retention_days: int) -> int:
    safe_retention_days = max(int(retention_days), 1)
    cutoff = datetime.now(UTC) - timedelta(days=safe_retention_days)
    deleted = AuditEvent.query.filter(AuditEvent.created_at < cutoff).delete(
        synchronize_session=False
    )
    db.session.commit()
    return int(deleted)


def serialize_audit_event(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "request_id": event.request_id,
        "method": event.method,
        "path": event.path,
        "status": event.status,
        "user_id": event.user_id,
        "ip": event.ip,
        "user_agent": event.user_agent,
        "created_at": event.created_at.isoformat(),
    }
