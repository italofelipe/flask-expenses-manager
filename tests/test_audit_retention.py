"""Tests for audit event retention (issue #1051)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.services.audit_event_service import purge_expired_audit_events

# ── purge_expired_audit_events ────────────────────────────────────────────────


class TestPurgeExpiredAuditEvents:
    def test_deletes_events_older_than_retention_window(self, app) -> None:
        """Rows older than retention_days must be removed from the DB."""
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent

        old_ts = datetime.now(UTC) - timedelta(days=95)
        recent_ts = datetime.now(UTC) - timedelta(days=10)

        with app.app_context():
            old_event = AuditEvent(
                method="GET",
                path="/old",
                status=200,
                created_at=old_ts,
            )
            recent_event = AuditEvent(
                method="GET",
                path="/recent",
                status=200,
                created_at=recent_ts,
            )
            db.session.add_all([old_event, recent_event])
            db.session.commit()

            deleted = purge_expired_audit_events(retention_days=90)

            assert deleted == 1
            remaining = AuditEvent.query.all()
            assert len(remaining) == 1
            assert remaining[0].path == "/recent"

    def test_returns_zero_when_nothing_to_purge(self, app) -> None:
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent

        with app.app_context():
            recent = AuditEvent(
                method="POST",
                path="/tx",
                status=201,
                created_at=datetime.now(UTC) - timedelta(days=5),
            )
            db.session.add(recent)
            db.session.commit()

            deleted = purge_expired_audit_events(retention_days=90)

            assert deleted == 0

    def test_minimum_retention_days_is_1(self, app) -> None:
        """Even with retention_days=0 the floor is 1 day — avoid accidental wipe."""
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent

        with app.app_context():
            old = AuditEvent(
                method="DELETE",
                path="/gone",
                status=204,
                created_at=datetime.now(UTC) - timedelta(days=30),
            )
            db.session.add(old)
            db.session.commit()

            # retention_days=0 should be coerced to 1
            deleted = purge_expired_audit_events(retention_days=0)
            assert deleted == 1

    def test_emits_prometheus_counter_when_rows_deleted(self, app) -> None:
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent

        with app.app_context():
            old = AuditEvent(
                method="GET",
                path="/metrics-test",
                status=200,
                created_at=datetime.now(UTC) - timedelta(days=200),
            )
            db.session.add(old)
            db.session.commit()

            with patch(
                "app.extensions.prometheus_metrics.record_audit_purge"
            ) as mock_metric:
                deleted = purge_expired_audit_events(retention_days=90)

            assert deleted == 1
            mock_metric.assert_called_once_with(1)

    def test_does_not_emit_metric_when_nothing_deleted(self, app) -> None:
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent

        with app.app_context():
            recent = AuditEvent(
                method="GET",
                path="/no-metric",
                status=200,
                created_at=datetime.now(UTC) - timedelta(days=1),
            )
            db.session.add(recent)
            db.session.commit()

            with patch(
                "app.extensions.prometheus_metrics.record_audit_purge"
            ) as mock_metric:
                deleted = purge_expired_audit_events(retention_days=90)

            assert deleted == 0
            mock_metric.assert_not_called()


# ── record_audit_purge metric ─────────────────────────────────────────────────


class TestRecordAuditPurgeMetric:
    def test_increments_counter_by_count(self) -> None:
        from app.extensions.prometheus_metrics import record_audit_purge

        # Should not raise even if prometheus_client registers a duplicate
        # counter in the same test process — the lazy-init is idempotent.
        record_audit_purge(42)  # no exception

    def test_zero_count_does_not_raise(self) -> None:
        from app.extensions.prometheus_metrics import record_audit_purge

        record_audit_purge(0)  # no exception


# ── audit_retention_cli ───────────────────────────────────────────────────────


class TestAuditRetentionCli:
    def test_purge_expired_command_reports_deleted_count(self, app) -> None:
        from click.testing import CliRunner

        from app.extensions.audit_retention_cli import register_audit_retention_commands

        with app.app_context():
            register_audit_retention_commands(app)

        runner = CliRunner()
        with patch(
            "app.extensions.audit_retention_cli.purge_expired_audit_events",
            return_value=7,
        ):
            result = runner.invoke(
                app.cli,
                ["audit-events", "purge-expired", "--retention-days", "30"],
                catch_exceptions=False,
                obj={"app": app},
            )

        assert result.exit_code == 0
        assert "deleted=7" in result.output
        assert "retention_days=30" in result.output

    def test_purge_expired_command_skips_when_disabled(self, app, monkeypatch) -> None:
        from click.testing import CliRunner

        from app.extensions.audit_retention_cli import register_audit_retention_commands

        monkeypatch.setenv("AUDIT_RETENTION_ENABLED", "false")

        with app.app_context():
            register_audit_retention_commands(app)

        runner = CliRunner()
        result = runner.invoke(
            app.cli,
            ["audit-events", "purge-expired"],
            catch_exceptions=False,
            obj={"app": app},
        )

        assert result.exit_code == 0
        assert "disabled" in result.output
