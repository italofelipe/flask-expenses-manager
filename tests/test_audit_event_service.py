from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.extensions.database import db
from app.models.audit_event import AuditEvent
from app.services.audit_event_service import (
    purge_expired_audit_events,
    search_audit_events_by_request_id,
)


def _new_event(
    *,
    request_id: str,
    created_at: datetime,
    path: str = "/auth/login",
) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        request_id=request_id,
        method="POST",
        path=path,
        status=200,
        user_id="user-1",
        ip="127.0.0.1",
        user_agent="pytest",
        created_at=created_at,
    )


def test_search_audit_events_by_request_id_returns_newest_first(app) -> None:
    now = datetime.now(UTC)
    older = _new_event(request_id="req-1", created_at=now - timedelta(minutes=5))
    newer = _new_event(request_id="req-1", created_at=now)
    other = _new_event(request_id="req-2", created_at=now)

    with app.app_context():
        db.session.add_all([older, newer, other])
        db.session.commit()

        found = search_audit_events_by_request_id("req-1", limit=10)
        assert [item.request_id for item in found] == ["req-1", "req-1"]
        assert [item.id for item in found] == [newer.id, older.id]


def test_purge_expired_audit_events_keeps_recent_rows(app) -> None:
    now = datetime.now(UTC)
    stale = _new_event(request_id="stale", created_at=now - timedelta(days=40))
    fresh = _new_event(request_id="fresh", created_at=now - timedelta(days=1))

    with app.app_context():
        db.session.add_all([stale, fresh])
        db.session.commit()

        deleted = purge_expired_audit_events(retention_days=30)
        assert deleted == 1

        remaining = AuditEvent.query.order_by(AuditEvent.request_id.asc()).all()
        assert len(remaining) == 1
        assert remaining[0].request_id == "fresh"
