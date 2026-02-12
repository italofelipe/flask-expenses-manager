from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pytest


def _create_docs_policy_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    flask_debug: bool,
    docs_policy: str | None,
):
    db_path = tmp_path / f"docs-policy-{uuid.uuid4().hex}.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("JWT_SECRET_KEY", "y" * 64)
    monkeypatch.setenv("FLASK_DEBUG", "true" if flask_debug else "false")
    monkeypatch.setenv("FLASK_TESTING", "true")
    monkeypatch.setenv("SECURITY_ENFORCE_STRONG_SECRETS", "false")
    monkeypatch.setenv("AUDIT_PERSISTENCE_ENABLED", "false")

    if docs_policy is None:
        monkeypatch.delenv("DOCS_EXPOSURE_POLICY", raising=False)
    else:
        monkeypatch.setenv("DOCS_EXPOSURE_POLICY", docs_policy)

    from app import create_app
    from app.extensions.database import db

    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app, db_path


def _dispose_docs_policy_app(app: Any, db_path: Path) -> None:
    from app.extensions.database import db

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
    if db_path.exists():
        db_path.unlink()


@contextmanager
def _docs_policy_app_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    flask_debug: bool,
    docs_policy: str | None,
) -> Generator[Any, None, None]:
    app, db_path = _create_docs_policy_app(
        monkeypatch,
        tmp_path,
        flask_debug=flask_debug,
        docs_policy=docs_policy,
    )
    try:
        yield app
    finally:
        _dispose_docs_policy_app(app, db_path)


def _register_and_login(client: Any, *, prefix: str) -> str:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@email.com"
    password = "StrongPass@123"
    register_response = client.post(
        "/auth/register",
        json={"name": prefix, "email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return str(login_response.get_json()["token"])


def test_docs_policy_defaults_to_authenticated_when_not_debug(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with _docs_policy_app_context(
        monkeypatch,
        tmp_path,
        flask_debug=False,
        docs_policy=None,
    ) as app:
        response = app.test_client().get("/docs/")
        assert response.status_code == 401
        assert response.get_json()["message"] == "Token inválido ou ausente"


def test_docs_policy_defaults_to_public_in_debug(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with _docs_policy_app_context(
        monkeypatch,
        tmp_path,
        flask_debug=True,
        docs_policy=None,
    ) as app:
        response = app.test_client().get("/docs/")
        assert response.status_code == 200


def test_docs_policy_can_disable_documentation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with _docs_policy_app_context(
        monkeypatch,
        tmp_path,
        flask_debug=False,
        docs_policy="disabled",
    ) as app:
        response = app.test_client().get("/docs/")
        assert response.status_code == 404


def test_docs_policy_authenticated_allows_jwt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with _docs_policy_app_context(
        monkeypatch,
        tmp_path,
        flask_debug=False,
        docs_policy="authenticated",
    ) as app:
        client = app.test_client()
        token = _register_and_login(client, prefix="docs-auth")

        response = client.get("/docs/", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
