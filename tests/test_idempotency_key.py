"""Tests for the Idempotency-Key middleware (SEC-GAP-05).

Tests run against a minimal Flask app with a fake in-memory Redis to avoid
any dependency on a real Redis instance.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest
from flask import Flask, jsonify

from app.middleware.idempotency_key import (
    IDEMPOTENCY_KEY_HEADER,
    register_idempotency_guard,
)

# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal in-memory Redis stub sufficient for middleware tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> bytes | None:
        with self._lock:
            return self._store.get(key)

    def set(self, key: str, value: Any, ex: int | None = None) -> None:
        with self._lock:
            self._store[key] = (
                value if isinstance(value, bytes) else str(value).encode()
            )

    def reset(self) -> None:
        with self._lock:
            self._store.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def minimal_app(fake_redis: FakeRedis) -> Flask:
    """Flask app with idempotency middleware wired to a fake Redis."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    # Patch _try_get_redis so it returns our fake
    import app.middleware.idempotency_key as mid_module

    original = mid_module._try_get_redis

    def _patched() -> FakeRedis:
        return fake_redis

    mid_module._try_get_redis = _patched  # type: ignore[assignment]
    register_idempotency_guard(app)
    mid_module._try_get_redis = original  # type: ignore[assignment]

    # Expose redis on extensions for assertions
    app.extensions["idempotency_redis"] = fake_redis

    @app.route("/payments/checkout", methods=["POST"])
    def checkout() -> Any:
        return jsonify({"order_id": "ord_123"}), 201

    @app.route("/things", methods=["POST"])
    def create_thing() -> Any:
        return jsonify({"id": "thing_1"}), 201

    @app.route("/subscriptions/checkout", methods=["POST"])
    def sub_checkout() -> Any:
        return jsonify({"subscription": "sub_abc"}), 201

    @app.route("/auth/login", methods=["POST"])
    def login() -> Any:
        return jsonify({"token": "jwt_xyz"}), 200

    return app


@pytest.fixture
def client(minimal_app: Flask):
    with minimal_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post(
    client: Any, path: str, body: dict | None = None, key: str | None = None
) -> Any:
    headers = {}
    if key:
        headers[IDEMPOTENCY_KEY_HEADER] = key
    return client.post(path, json=body or {}, headers=headers)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIdempotencyDuplicatePost:
    """Same key → same response, handler called once."""

    def test_two_posts_same_key_return_same_response(self, client: Any) -> None:
        key = "unique-key-abc"
        first = _post(client, "/payments/checkout", {"amount": 100}, key=key)
        second = _post(client, "/payments/checkout", {"amount": 100}, key=key)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.get_json() == second.get_json()

    def test_replayed_response_has_replay_header(self, client: Any) -> None:
        key = "replay-header-key"
        _post(client, "/payments/checkout", {"amount": 50}, key=key)
        second = _post(client, "/payments/checkout", {"amount": 50}, key=key)

        assert second.headers.get("X-Idempotency-Replayed") == "true"

    def test_first_response_has_no_replay_header(self, client: Any) -> None:
        key = "first-call-key"
        first = _post(client, "/payments/checkout", {"amount": 50}, key=key)
        assert "X-Idempotency-Replayed" not in first.headers

    def test_different_keys_execute_independently(self, client: Any) -> None:
        first = _post(client, "/things", {"name": "A"}, key="key-one")
        second = _post(client, "/things", {"name": "B"}, key="key-two")

        assert first.status_code == 201
        assert second.status_code == 201
        # Both reach the handler — both get 201 (handler is idempotent here)
        assert first.get_json() == second.get_json()


class TestIdempotencyConflict:
    """Same key + different body → 409."""

    def test_same_key_different_body_returns_409(self, client: Any) -> None:
        key = "conflict-key"
        _post(client, "/payments/checkout", {"amount": 100}, key=key)
        conflict = _post(client, "/payments/checkout", {"amount": 999}, key=key)

        assert conflict.status_code == 409
        body = conflict.get_json()
        assert body["error"] == "IDEMPOTENCY_CONFLICT"


class TestRequiredEndpoints:
    """Endpoints in REQUIRED_PREFIXES must reject missing key with 400."""

    def test_required_endpoint_without_key_returns_400(self, client: Any) -> None:
        response = _post(client, "/subscriptions/checkout", {"plan": "pro"})
        assert response.status_code == 400
        body = response.get_json()
        assert body["error"] == "IDEMPOTENCY_KEY_REQUIRED"

    def test_required_endpoint_with_key_succeeds(self, client: Any) -> None:
        response = _post(
            client, "/subscriptions/checkout", {"plan": "pro"}, key="sub-key-1"
        )
        assert response.status_code == 201


class TestSkippedEndpoints:
    """Auth and webhook-like paths are never intercepted."""

    def test_auth_login_no_key_not_blocked(self, client: Any) -> None:
        response = _post(client, "/auth/login", {"email": "a@b.com", "password": "pw"})
        # Middleware doesn't block or require key on /auth/*
        assert response.status_code == 200

    def test_non_post_methods_not_intercepted(self, client: Any) -> None:
        # GET never hits the idempotency guard
        response = client.get("/things")
        # 405 because /things only allows POST — that's fine; the point is
        # the middleware didn't return anything for a GET
        assert response.status_code in {200, 404, 405}


class TestNoKeyOptional:
    """POST without Idempotency-Key on non-required endpoints is fine."""

    def test_post_without_key_on_optional_endpoint_succeeds(self, client: Any) -> None:
        response = _post(client, "/payments/checkout", {"amount": 42})
        assert response.status_code == 201

    def test_two_posts_without_key_both_execute(self, client: Any) -> None:
        first = _post(client, "/things", {"name": "X"})
        second = _post(client, "/things", {"name": "X"})
        # Neither is cached — both reach the handler
        assert first.status_code == 201
        assert second.status_code == 201
        assert "X-Idempotency-Replayed" not in first.headers
        assert "X-Idempotency-Replayed" not in second.headers


class TestRedisUnavailable:
    """When Redis is unavailable the middleware is a no-op (fail-open)."""

    def test_middleware_disabled_when_redis_unavailable(self) -> None:
        import app.middleware.idempotency_key as mid_module

        original = mid_module._try_get_redis

        def _fail() -> None:
            return None

        mid_module._try_get_redis = _fail  # type: ignore[assignment]
        try:
            app_no_redis = Flask(__name__)
            app_no_redis.config["TESTING"] = True
            register_idempotency_guard(app_no_redis)

            @app_no_redis.route("/items", methods=["POST"])
            def create_item() -> Any:
                return jsonify({"ok": True}), 201

            with app_no_redis.test_client() as c:
                # Both calls hit the handler — no idempotency enforcement
                r1 = c.post("/items", json={}, headers={IDEMPOTENCY_KEY_HEADER: "k1"})
                r2 = c.post("/items", json={}, headers={IDEMPOTENCY_KEY_HEADER: "k1"})
                assert r1.status_code == 201
                assert r2.status_code == 201
                assert "X-Idempotency-Replayed" not in r2.headers
        finally:
            mid_module._try_get_redis = original  # type: ignore[assignment]
