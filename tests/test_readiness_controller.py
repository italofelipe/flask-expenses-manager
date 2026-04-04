"""
Tests for GET /readiness (B19).

Scenarios:
- All dependencies healthy → 200, status=ready
- DB unreachable → 503, status=degraded
- Redis unreachable → 503, status=degraded
- Missing/invalid bearer token when READINESS_TOKEN is set → 401
- No READINESS_TOKEN configured → open access (200)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(client: Any, token: str | None = None) -> Any:
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.get("/readiness", headers=headers)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_readiness_all_healthy_returns_200(client: Any) -> None:
    """When DB and Redis probes succeed the endpoint returns 200 and status=ready."""
    with (
        patch(
            "app.controllers.health_controller._check_db",
            return_value="ok",
        ),
        patch(
            "app.controllers.health_controller._check_redis",
            return_value="ok",
        ),
    ):
        resp = _get(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ready"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


# ---------------------------------------------------------------------------
# DB down
# ---------------------------------------------------------------------------


def test_readiness_db_down_returns_503(client: Any) -> None:
    """When the DB probe fails the endpoint returns 503 and status=degraded."""
    with (
        patch(
            "app.controllers.health_controller._check_db",
            return_value="error",
        ),
        patch(
            "app.controllers.health_controller._check_redis",
            return_value="ok",
        ),
    ):
        resp = _get(client)

    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
    assert body["redis"] == "ok"


# ---------------------------------------------------------------------------
# Redis down
# ---------------------------------------------------------------------------


def test_readiness_redis_down_returns_503(client: Any) -> None:
    """When the Redis probe fails the endpoint returns 503 and status=degraded."""
    with (
        patch(
            "app.controllers.health_controller._check_db",
            return_value="ok",
        ),
        patch(
            "app.controllers.health_controller._check_redis",
            return_value="error",
        ),
    ):
        resp = _get(client)

    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "degraded"
    assert body["db"] == "ok"
    assert body["redis"] == "error"


# ---------------------------------------------------------------------------
# Both dependencies down
# ---------------------------------------------------------------------------


def test_readiness_both_down_returns_503(client: Any) -> None:
    """When both DB and Redis fail the endpoint returns 503."""
    with (
        patch(
            "app.controllers.health_controller._check_db",
            return_value="error",
        ),
        patch(
            "app.controllers.health_controller._check_redis",
            return_value="error",
        ),
    ):
        resp = _get(client)

    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "degraded"


# ---------------------------------------------------------------------------
# Bearer token protection
# ---------------------------------------------------------------------------


def test_readiness_token_required_when_configured(client: Any, monkeypatch) -> None:
    """When READINESS_TOKEN is set, requests without a token are rejected."""
    monkeypatch.setenv("READINESS_TOKEN", "super-secret-probe-token")

    resp = _get(client)  # no token

    assert resp.status_code == 401


def test_readiness_invalid_token_rejected(client: Any, monkeypatch) -> None:
    """A wrong token is rejected with 401."""
    monkeypatch.setenv("READINESS_TOKEN", "correct-token")

    resp = _get(client, token="wrong-token")

    assert resp.status_code == 401


def test_readiness_valid_token_accepted(client: Any, monkeypatch) -> None:
    """A correct bearer token is accepted and the probe executes normally."""
    monkeypatch.setenv("READINESS_TOKEN", "correct-token")

    with (
        patch(
            "app.controllers.health_controller._check_db",
            return_value="ok",
        ),
        patch(
            "app.controllers.health_controller._check_redis",
            return_value="ok",
        ),
    ):
        resp = _get(client, token="correct-token")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ready"


def test_readiness_open_when_no_token_configured(client: Any, monkeypatch) -> None:
    """When READINESS_TOKEN is not set any request is accepted."""
    monkeypatch.delenv("READINESS_TOKEN", raising=False)

    with (
        patch(
            "app.controllers.health_controller._check_db",
            return_value="ok",
        ),
        patch(
            "app.controllers.health_controller._check_redis",
            return_value="ok",
        ),
    ):
        resp = _get(client)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Internal probe unit tests
# ---------------------------------------------------------------------------


def test_check_db_returns_ok_on_success(app: Any) -> None:
    """_check_db returns 'ok' when the DB is reachable."""
    from app.controllers.health_controller import _check_db

    with app.app_context():
        result = _check_db()

    assert result == "ok"


def test_check_db_returns_error_on_exception(app: Any) -> None:
    """_check_db returns 'error' when the DB query raises."""
    from app.controllers.health_controller import _check_db
    from app.extensions.database import db

    with app.app_context():
        with patch.object(db.session, "execute", side_effect=Exception("db down")):
            result = _check_db()

    assert result == "error"


def test_check_redis_returns_ok_when_no_url_configured(app: Any, monkeypatch) -> None:
    """_check_redis returns 'ok' when no Redis URL is configured (optional dep)."""
    from app.controllers.health_controller import _check_redis

    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("LOGIN_GUARD_REDIS_URL", raising=False)

    with app.app_context():
        result = _check_redis()

    assert result == "ok"


def test_check_redis_returns_error_when_ping_fails(app: Any, monkeypatch) -> None:
    """_check_redis returns 'error' when redis.ping() raises."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    mock_client = MagicMock()
    mock_client.ping.side_effect = Exception("connection refused")

    mock_redis_cls = MagicMock(return_value=mock_client)
    mock_redis_cls.from_url = MagicMock(return_value=mock_client)

    mock_redis_mod = MagicMock()
    mock_redis_mod.Redis = mock_redis_cls

    with app.app_context():
        with patch(
            "app.controllers.health_controller.importlib.import_module",
            return_value=mock_redis_mod,
        ):
            from app.controllers.health_controller import _check_redis  # noqa: PLC0415

            result = _check_redis()

    assert result == "error"
