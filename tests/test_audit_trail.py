import logging

import pytest
from flask import Flask

from app.extensions.audit_trail import _is_sensitive_path, register_audit_trail
from app.models.audit_event import AuditEvent


def test_is_sensitive_path_matches_prefixes() -> None:
    prefixes = ("/auth/", "/wallet", "/graphql")
    assert _is_sensitive_path("/auth/login", prefixes) is True
    assert _is_sensitive_path("/wallet/123", prefixes) is True
    assert _is_sensitive_path("/graphql", prefixes) is True
    assert _is_sensitive_path("/health", prefixes) is False


def test_register_audit_trail_logs_only_sensitive_routes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.get("/health")
    def _health() -> tuple[str, int]:
        return "ok", 200

    @app.get("/auth/login")
    def _login() -> tuple[str, int]:
        return "ok", 200

    register_audit_trail(app)

    client = app.test_client()
    with caplog.at_level(logging.INFO):
        client.get("/health")
        client.get("/auth/login")

    audit_logs = [
        record.message for record in caplog.records if "audit_trail " in record.message
    ]
    assert len(audit_logs) == 1
    assert '"path": "/auth/login"' in audit_logs[0]
    assert '"status": 200' in audit_logs[0]


def test_audit_trail_persists_event_when_enabled(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUDIT_PERSISTENCE_ENABLED", "true")

    response = client.post(
        "/auth/register",
        json={
            "name": "audit-user",
            "email": "audit-user@email.com",
            "password": "StrongPass@123",
        },
    )
    assert response.status_code == 201

    with app.app_context():
        event = AuditEvent.query.filter_by(path="/auth/register").first()
        assert event is not None
        assert event.method == "POST"
