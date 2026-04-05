"""Tests for GET /dashboard/trends endpoint (#887)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    resp = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert resp.status_code == 201

    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.get_json()["token"]


def _auth(token: str, contract: str = "v2") -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract:
        headers["X-API-Contract"] = contract
    return headers


def _create_paid_transaction(
    client, token: str, *, title: str, amount: str, tx_type: str, due_date: str
) -> None:
    """Create a transaction and mark it paid via PATCH."""
    resp = client.post(
        "/transactions",
        headers=_auth(token),
        json={
            "title": title,
            "amount": amount,
            "type": tx_type,
            "due_date": due_date,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    # Support both legacy (top-level "transaction") and v2 ("data.transaction") shapes
    tx_raw = body.get("data", {}).get("transaction") or body.get("transaction")
    tx_id = tx_raw[0]["id"] if isinstance(tx_raw, list) else tx_raw["id"]

    # Mark paid via PATCH with paid_at (required when status=paid)
    paid_at = datetime.now(UTC).isoformat()
    resp = client.patch(
        f"/transactions/{tx_id}",
        headers=_auth(token),
        json={"status": "paid", "paid_at": paid_at},
    )
    assert resp.status_code == 200, resp.get_json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trends_returns_200_with_series(client) -> None:
    token = _register_and_login(client, "trends-basic")
    today = date.today()
    due = today.replace(day=1).isoformat()

    _create_paid_transaction(
        client, token, title="Salário", amount="5000.00", tx_type="income", due_date=due
    )

    resp = client.get("/dashboard/trends", headers=_auth(token))
    assert resp.status_code == 200

    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    assert "months" in data
    assert "series" in data
    assert data["months"] == 6
    # At least the current month should appear
    assert len(data["series"]) >= 1
    entry = data["series"][0]
    assert "month" in entry
    assert "income" in entry
    assert "expenses" in entry
    assert "balance" in entry


def test_trends_months_param_12(client) -> None:
    token = _register_and_login(client, "trends-12m")
    resp = client.get("/dashboard/trends?months=12", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["months"] == 12


def test_trends_months_0_returns_422(client) -> None:
    token = _register_and_login(client, "trends-zero")
    resp = client.get("/dashboard/trends?months=0", headers=_auth(token))
    assert resp.status_code == 422


def test_trends_months_25_returns_422(client) -> None:
    token = _register_and_login(client, "trends-25")
    resp = client.get("/dashboard/trends?months=25", headers=_auth(token))
    assert resp.status_code == 422


def test_trends_empty_database_returns_empty_series(client) -> None:
    token = _register_and_login(client, "trends-empty")
    resp = client.get("/dashboard/trends?months=3", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["series"] == []


def test_trends_caching(client, app) -> None:
    """Second call returns X-Cache: HIT when cache is available."""
    from app.services import cache_service as cs

    class _FakeCache:
        def __init__(self) -> None:
            self._store: dict = {}

        def get(self, key: str):
            return self._store.get(key)

        def set(self, key: str, value, *, ttl: int) -> None:
            self._store[key] = value

        def invalidate(self, key: str) -> None:
            self._store.pop(key, None)

        def invalidate_pattern(self, pattern: str) -> None:
            pass

        @property
        def available(self) -> bool:
            return True

    original = cs._cache_instance
    fake_cache = _FakeCache()
    cs._cache_instance = fake_cache

    try:
        token = _register_and_login(client, "trends-cache")

        resp1 = client.get("/dashboard/trends?months=3", headers=_auth(token))
        assert resp1.status_code == 200
        assert resp1.headers.get("X-Cache") == "MISS"

        resp2 = client.get("/dashboard/trends?months=3", headers=_auth(token))
        assert resp2.status_code == 200
        assert resp2.headers.get("X-Cache") == "HIT"
    finally:
        cs._cache_instance = original


def test_trends_unauthenticated_returns_401(client) -> None:
    resp = client.get("/dashboard/trends")
    assert resp.status_code == 401
