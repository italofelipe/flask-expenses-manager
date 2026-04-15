"""Tests for soft-delete audit trail (issue #1052)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator
from unittest.mock import patch
from uuid import uuid4

import pytest

# ── Admin app fixture (auth guard disabled) ───────────────────────────────────

_TEST_ENV = {
    "SECRET_KEY": "test-secret-key-with-64-chars-minimum-for-jwt-signing-0001",
    "JWT_SECRET_KEY": "test-jwt-secret-key-with-64-chars-minimum-for-signing-0002",
    "FLASK_TESTING": "true",
    "SECURITY_ENFORCE_STRONG_SECRETS": "false",
    "DOCS_EXPOSURE_POLICY": "public",
    "CORS_ALLOWED_ORIGINS": "https://frontend.local",
    "GRAPHQL_ALLOW_INTROSPECTION": "true",
    "BILLING_WEBHOOK_ALLOW_UNSIGNED": "true",
}


@pytest.fixture()
def admin_app(tmp_path: Path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    for k, v in _TEST_ENV.items():
        os.environ[k] = v

    from app import create_app
    from app.extensions.database import db

    flask_app = create_app(enable_http_runtime=False)
    flask_app.config["TESTING"] = True

    with flask_app.app_context():
        db.drop_all()
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def admin_client(admin_app) -> Generator:
    with admin_app.test_client() as c:
        yield c


# ── record_entity_delete ──────────────────────────────────────────────────────


class TestRecordEntityDelete:
    def test_persists_audit_event_when_persistence_enabled(self, app) -> None:
        from app.extensions.audit_trail import record_entity_delete

        with app.app_context():
            from app.extensions.database import db
            from app.models.audit_event import AuditEvent

            entity_id = str(uuid4())
            actor_id = str(uuid4())

            with patch(
                "app.extensions.audit_trail._is_audit_persistence_enabled",
                return_value=True,
            ):
                record_entity_delete(
                    entity_type="transaction",
                    entity_id=entity_id,
                    actor_id=actor_id,
                )
                db.session.commit()

            events = AuditEvent.query.filter_by(
                entity_type="transaction", entity_id=entity_id
            ).all()
            assert len(events) == 1
            event = events[0]
            assert event.action == "soft_delete"
            assert event.actor_id == actor_id
            assert event.method == "SYSTEM"

    def test_noop_when_persistence_disabled(self, app) -> None:
        from app.extensions.audit_trail import record_entity_delete

        with app.app_context():
            from app.models.audit_event import AuditEvent

            entity_id = str(uuid4())

            with patch(
                "app.extensions.audit_trail._is_audit_persistence_enabled",
                return_value=False,
            ):
                record_entity_delete(
                    entity_type="transaction",
                    entity_id=entity_id,
                    actor_id=None,
                )

            events = AuditEvent.query.filter_by(entity_id=entity_id).all()
            assert events == []

    def test_extra_field_stored(self, app) -> None:
        from app.extensions.audit_trail import record_entity_delete

        with app.app_context():
            from app.extensions.database import db
            from app.models.audit_event import AuditEvent

            entity_id = str(uuid4())
            extra_payload = json.dumps({"reason": "test", "deleted_at": "2026-04-15"})

            with patch(
                "app.extensions.audit_trail._is_audit_persistence_enabled",
                return_value=True,
            ):
                record_entity_delete(
                    entity_type="user",
                    entity_id=entity_id,
                    actor_id=None,
                    extra=extra_payload,
                )
                db.session.commit()

            event = AuditEvent.query.filter_by(entity_id=entity_id).first()
            assert event is not None
            assert event.extra == extra_payload


# ── list_entity_audit_events ──────────────────────────────────────────────────


class TestListEntityAuditEvents:
    def test_returns_events_for_entity(self, app) -> None:
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent
        from app.services.audit_event_service import list_entity_audit_events

        with app.app_context():
            entity_id = str(uuid4())
            for _ in range(3):
                db.session.add(
                    AuditEvent(
                        method="SYSTEM",
                        path="",
                        status=0,
                        entity_type="transaction",
                        entity_id=entity_id,
                        action="soft_delete",
                    )
                )
            db.session.commit()

            results = list_entity_audit_events("transaction", entity_id)
            assert len(results) == 3

    def test_returns_empty_for_unknown_entity(self, app) -> None:
        from app.services.audit_event_service import list_entity_audit_events

        with app.app_context():
            results = list_entity_audit_events("transaction", str(uuid4()))
            assert results == []

    def test_limit_respected(self, app) -> None:
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent
        from app.services.audit_event_service import list_entity_audit_events

        with app.app_context():
            entity_id = str(uuid4())
            for _ in range(10):
                db.session.add(
                    AuditEvent(
                        method="SYSTEM",
                        path="",
                        status=0,
                        entity_type="user",
                        entity_id=entity_id,
                        action="soft_delete",
                    )
                )
            db.session.commit()

            results = list_entity_audit_events("user", entity_id, limit=5)
            assert len(results) == 5


# ── admin audit trail endpoint ────────────────────────────────────────────────


class TestAdminAuditTrailEndpoint:
    def test_returns_events_for_known_entity(self, admin_client, admin_app) -> None:
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent

        with admin_app.app_context():
            entity_id = str(uuid4())
            db.session.add(
                AuditEvent(
                    method="SYSTEM",
                    path="",
                    status=0,
                    entity_type="transaction",
                    entity_id=entity_id,
                    action="soft_delete",
                    actor_id="user-abc",
                )
            )
            db.session.commit()

        with patch(
            "app.controllers.admin.audit_trail._is_admin",
            return_value=True,
        ):
            resp = admin_client.get(f"/admin/audit-trail/transaction/{entity_id}")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1
        assert body["events"][0]["action"] == "soft_delete"

    def test_returns_400_for_unknown_entity_type(self, admin_client) -> None:
        with patch(
            "app.controllers.admin.audit_trail._is_admin",
            return_value=True,
        ):
            resp = admin_client.get(f"/admin/audit-trail/invoice/{uuid4()}")

        assert resp.status_code == 400
        assert resp.get_json()["code"] == "INVALID_ENTITY_TYPE"

    def test_returns_403_for_non_admin(self, admin_client) -> None:
        with patch(
            "app.controllers.admin.audit_trail._is_admin",
            return_value=False,
        ):
            resp = admin_client.get(f"/admin/audit-trail/transaction/{uuid4()}")

        assert resp.status_code == 403

    def test_returns_empty_list_for_entity_with_no_events(self, admin_client) -> None:
        with patch(
            "app.controllers.admin.audit_trail._is_admin",
            return_value=True,
        ):
            resp = admin_client.get(f"/admin/audit-trail/user/{uuid4()}")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 0
        assert body["events"] == []
