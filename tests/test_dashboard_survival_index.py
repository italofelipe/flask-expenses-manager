"""Tests for GET /dashboard/survival-index (issue #1024).

Covers:
- Unauthenticated returns 401
- New user with no data returns graceful null (no expenses)
- User with wallet + paid expenses returns correct index and classification
- Classification boundaries: critical <3, attention 3-6, comfortable 6-12, secure >12
- Zero assets returns survival_months = 0
- Service unit: _classify_survival helper
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.application.services.transaction_query_service import _classify_survival
from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.wallet import Wallet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.get_json()["token"]
    profile = client.get(
        "/user/profile", headers={"Authorization": f"Bearer {token}"}
    ).get_json()
    user_id = profile.get("data", {}).get("id") or profile.get("user", {}).get("id")
    return token, user_id


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_wallet(app, user_id: str, *, value: str) -> None:
    with app.app_context():
        w = Wallet(
            user_id=uuid.UUID(user_id),
            name="Test Asset",
            value=Decimal(value),
            should_be_on_wallet=True,
            asset_class="custom",
            register_date=date(2026, 1, 1),
        )
        db.session.add(w)
        db.session.commit()


def _seed_paid_expense(app, user_id: str, *, amount: str, due_date: date) -> None:
    with app.app_context():
        tx = Transaction(
            user_id=uuid.UUID(user_id),
            title="Expense",
            amount=Decimal(amount),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PAID,
            due_date=due_date,
            paid_at=datetime.now(UTC),
        )
        db.session.add(tx)
        db.session.commit()


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


class TestSurvivalIndexAuth:
    def test_unauthenticated_returns_401(self, client) -> None:
        resp = client.get("/dashboard/survival-index")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# No data edge cases
# ---------------------------------------------------------------------------


class TestSurvivalIndexNoData:
    def test_no_expenses_returns_null_survival(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="si-noexp")
        _seed_wallet(app, user_id, value="50000.00")

        resp = client.get("/dashboard/survival-index", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        assert data["survival_months"] is None
        assert data["classification"] is None
        assert data["total_assets"] == 50000.0

    def test_no_assets_returns_zero_or_null(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="si-noasset")
        today = date.today()
        # Seed one paid expense in the last 3 months
        prev = today.replace(day=1)
        y = prev.year if prev.month > 1 else prev.year - 1
        m = prev.month - 1 if prev.month > 1 else 12
        exp_date = date(y, m, 15)
        _seed_paid_expense(app, user_id, amount="1000.00", due_date=exp_date)

        resp = client.get("/dashboard/survival-index", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        assert data["total_assets"] == 0.0
        assert data["survival_months"] == 0.0

    def test_new_user_no_data_is_graceful(self, app, client) -> None:
        token, _uid = _register_and_login(client, prefix="si-new")
        resp = client.get("/dashboard/survival-index", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        assert data["survival_months"] is None
        assert data["total_assets"] == 0.0
        assert data["avg_monthly_expense"] == 0.0
        assert data["period_analyzed_months"] == 3


# ---------------------------------------------------------------------------
# Correct calculation
# ---------------------------------------------------------------------------


class TestSurvivalIndexCalculation:
    def test_correct_index_calculation(self, app, client) -> None:
        """45000 assets / (3000/month avg) = 15 months → secure."""
        token, user_id = _register_and_login(client, prefix="si-calc")
        _seed_wallet(app, user_id, value="45000.00")

        today = date.today()
        for i in range(1, 4):  # 3 previous months
            y, m = today.year, today.month - i
            while m <= 0:
                m += 12
                y -= 1
            _seed_paid_expense(app, user_id, amount="3000.00", due_date=date(y, m, 15))

        resp = client.get("/dashboard/survival-index", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        assert data["total_assets"] == 45000.0
        assert data["avg_monthly_expense"] == 3000.0
        assert data["survival_months"] == 15.0
        assert data["classification"] == "secure"

    def test_response_has_all_required_keys(self, app, client) -> None:
        token, _uid = _register_and_login(client, prefix="si-keys")
        resp = client.get("/dashboard/survival-index", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        required = {
            "survival_months",
            "total_assets",
            "avg_monthly_expense",
            "classification",
            "period_analyzed_months",
        }
        assert required.issubset(data.keys())


# ---------------------------------------------------------------------------
# Classification unit tests
# ---------------------------------------------------------------------------


class TestClassifySurvival:
    def test_critical(self) -> None:
        assert _classify_survival(0.0) == "critical"
        assert _classify_survival(2.9) == "critical"

    def test_attention(self) -> None:
        assert _classify_survival(3.0) == "attention"
        assert _classify_survival(5.9) == "attention"

    def test_comfortable(self) -> None:
        assert _classify_survival(6.0) == "comfortable"
        assert _classify_survival(12.0) == "comfortable"

    def test_secure(self) -> None:
        assert _classify_survival(12.1) == "secure"
        assert _classify_survival(100.0) == "secure"
