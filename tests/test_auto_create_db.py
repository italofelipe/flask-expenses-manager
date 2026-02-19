from __future__ import annotations

from app import create_app
from app.extensions.database import db


def test_create_app_does_not_auto_create_db_without_explicit_flag(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("AUTO_CREATE_DB", raising=False)

    calls = {"count": 0}

    def _fake_create_all() -> None:
        calls["count"] += 1

    monkeypatch.setattr(db, "create_all", _fake_create_all)

    create_app()

    assert calls["count"] == 0


def test_create_app_auto_create_db_runs_when_explicitly_enabled(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("AUTO_CREATE_DB", "true")

    calls = {"count": 0}

    def _fake_create_all() -> None:
        calls["count"] += 1

    monkeypatch.setattr(db, "create_all", _fake_create_all)

    create_app()

    assert calls["count"] == 1
