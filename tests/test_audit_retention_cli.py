from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.extensions.database import db
from app.models.audit_event import AuditEvent


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


def test_audit_retention_cli_purge_expired_deletes_stale_events(app) -> None:
    now = datetime.now(UTC)
    stale = _new_event(request_id="stale-cli", created_at=now - timedelta(days=40))
    fresh = _new_event(request_id="fresh-cli", created_at=now - timedelta(days=1))

    with app.app_context():
        db.session.add_all([stale, fresh])
        db.session.commit()

    result = app.test_cli_runner().invoke(
        args=["audit-events", "purge-expired", "--retention-days", "30"]
    )
    assert result.exit_code == 0
    assert "deleted=1 retention_days=30" in result.output

    with app.app_context():
        remaining = AuditEvent.query.order_by(AuditEvent.request_id.asc()).all()
        assert len(remaining) == 1
        assert remaining[0].request_id == "fresh-cli"


def test_audit_retention_cli_uses_env_default_days(app, monkeypatch) -> None:
    now = datetime.now(UTC)
    stale = _new_event(request_id="stale-env", created_at=now - timedelta(days=10))

    with app.app_context():
        db.session.add(stale)
        db.session.commit()

    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "7")
    result = app.test_cli_runner().invoke(args=["audit-events", "purge-expired"])
    assert result.exit_code == 0
    assert "deleted=1 retention_days=7" in result.output


def test_audit_retention_cli_skips_when_disabled(app, monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_RETENTION_ENABLED", "false")

    result = app.test_cli_runner().invoke(args=["audit-events", "purge-expired"])
    assert result.exit_code == 0
    assert "audit retention disabled" in result.output


def test_audit_retention_cli_normalizes_non_positive_days(app) -> None:
    result = app.test_cli_runner().invoke(
        args=["audit-events", "purge-expired", "--retention-days", "0"]
    )
    assert result.exit_code == 0
    assert "retention_days=1" in result.output


def test_audit_retention_cli_fails_on_invalid_days_type(app) -> None:
    result = app.test_cli_runner().invoke(
        args=["audit-events", "purge-expired", "--retention-days", "invalid"]
    )
    assert result.exit_code == 2
    assert "Invalid value for '--retention-days'" in result.output
