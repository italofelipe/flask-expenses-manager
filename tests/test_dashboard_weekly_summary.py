"""Tests for GET /dashboard/weekly-summary (B13)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _create_paid_tx(
    client, token: str, *, title: str, amount: str, tx_type: str, due_date: str
) -> None:
    resp = client.post(
        "/transactions",
        headers=_auth(token),
        json={"title": title, "amount": amount, "type": tx_type, "due_date": due_date},
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    tx_raw = body.get("data", {}).get("transaction") or body.get("transaction")
    tx_id = tx_raw[0]["id"] if isinstance(tx_raw, list) else tx_raw["id"]
    paid_at = datetime.now(UTC).isoformat()
    resp = client.patch(
        f"/transactions/{tx_id}",
        headers=_auth(token),
        json={"status": "paid", "paid_at": paid_at},
    )
    assert resp.status_code == 200, resp.get_json()


class TestWeeklySummaryValidation:
    def test_requires_auth(self, client):
        resp = client.get("/dashboard/weekly-summary")
        assert resp.status_code == 401

    def test_invalid_period_returns_422(self, client):
        token = _register_and_login(client, "period-err")
        resp = client.get("/dashboard/weekly-summary?period=2y", headers=_auth(token))
        assert resp.status_code == 422

    def test_custom_period_missing_end_date_returns_422(self, client):
        token = _register_and_login(client, "custom-err")
        resp = client.get(
            "/dashboard/weekly-summary?start_date=2026-01-01",
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_start_after_end_returns_422(self, client):
        token = _register_and_login(client, "order-err")
        resp = client.get(
            "/dashboard/weekly-summary?start_date=2026-04-20&end_date=2026-04-01",
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_invalid_date_format_returns_422(self, client):
        token = _register_and_login(client, "fmt-err")
        resp = client.get(
            "/dashboard/weekly-summary?start_date=20260101&end_date=20260131",
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestWeeklySummaryResponse:
    def test_default_period_returns_correct_shape(self, client):
        token = _register_and_login(client, "shape")
        resp = client.get("/dashboard/weekly-summary", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "current_week" in data
        assert "previous_week" in data
        assert "comparison" in data
        assert "series" in data
        assert data["period"] == "1m"
        assert "series_start" in data
        assert "series_end" in data

    def test_current_week_fields(self, client):
        token = _register_and_login(client, "cw-fields")
        resp = client.get("/dashboard/weekly-summary", headers=_auth(token))
        cw = resp.get_json()["data"]["current_week"]
        expected = ("start", "end", "income", "expense", "balance", "transaction_count")
        for field in expected:
            assert field in cw, f"Missing field: {field}"

    def test_comparison_fields(self, client):
        token = _register_and_login(client, "cmp-fields")
        resp = client.get("/dashboard/weekly-summary", headers=_auth(token))
        cmp = resp.get_json()["data"]["comparison"]
        for field in (
            "income_delta",
            "income_delta_percent",
            "expense_delta",
            "expense_delta_percent",
            "balance_delta",
            "balance_delta_percent",
        ):
            assert field in cmp, f"Missing field: {field}"

    def test_3m_period_accepted(self, client):
        token = _register_and_login(client, "3m-period")
        resp = client.get("/dashboard/weekly-summary?period=3m", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["period"] == "3m"

    def test_6m_period_accepted(self, client):
        token = _register_and_login(client, "6m-period")
        resp = client.get("/dashboard/weekly-summary?period=6m", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["period"] == "6m"

    def test_custom_period_accepted(self, client):
        token = _register_and_login(client, "custom-ok")
        resp = client.get(
            "/dashboard/weekly-summary?start_date=2026-01-01&end_date=2026-01-31",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["period"] == "custom"
        assert data["series_start"] == "2026-01-01"
        assert data["series_end"] == "2026-01-31"

    def test_series_daily_for_1m(self, client):
        token = _register_and_login(client, "series-daily")
        resp = client.get("/dashboard/weekly-summary?period=1m", headers=_auth(token))
        assert resp.status_code == 200
        series = resp.get_json()["data"]["series"]
        # 1m = 30 days → 30 daily entries
        assert len(series) == 30
        entry = series[0]
        for field in ("date", "income", "expense", "balance"):
            assert field in entry

    def test_series_weekly_for_3m(self, client):
        token = _register_and_login(client, "series-weekly")
        resp = client.get("/dashboard/weekly-summary?period=3m", headers=_auth(token))
        assert resp.status_code == 200
        series = resp.get_json()["data"]["series"]
        # 3m = 90 days > 31 → weekly buckets (≈13 weeks)
        assert len(series) > 0
        assert len(series) < 50  # weekly buckets, not daily


class TestWeeklySummaryWithData:
    def test_income_reflected_in_current_week(self, client):
        token = _register_and_login(client, "income-data")
        today = date.today().isoformat()
        _create_paid_tx(
            client,
            token,
            title="Salário",
            amount="3000.00",
            tx_type="income",
            due_date=today,
        )
        resp = client.get("/dashboard/weekly-summary", headers=_auth(token))
        cw = resp.get_json()["data"]["current_week"]
        assert cw["income"] == pytest.approx(3000.0)
        assert cw["transaction_count"] >= 1

    def test_expense_reflected_in_current_week(self, client):
        token = _register_and_login(client, "expense-data")
        today = date.today().isoformat()
        _create_paid_tx(
            client,
            token,
            title="Aluguel",
            amount="1500.00",
            tx_type="expense",
            due_date=today,
        )
        resp = client.get("/dashboard/weekly-summary", headers=_auth(token))
        cw = resp.get_json()["data"]["current_week"]
        assert cw["expense"] == pytest.approx(1500.0)
        assert cw["balance"] == pytest.approx(-1500.0)

    def test_delta_percent_null_when_previous_zero(self, client):
        token = _register_and_login(client, "delta-null")
        today = date.today().isoformat()
        _create_paid_tx(
            client,
            token,
            title="Receita",
            amount="500.00",
            tx_type="income",
            due_date=today,
        )
        resp = client.get("/dashboard/weekly-summary", headers=_auth(token))
        cmp = resp.get_json()["data"]["comparison"]
        # no previous week data → percent should be None
        assert cmp["income_delta_percent"] is None

    def test_series_entry_matches_transaction_date(self, client):
        token = _register_and_login(client, "series-match")
        today = date.today().isoformat()
        _create_paid_tx(
            client,
            token,
            title="Compra",
            amount="200.00",
            tx_type="expense",
            due_date=today,
        )
        resp = client.get("/dashboard/weekly-summary?period=1m", headers=_auth(token))
        series = resp.get_json()["data"]["series"]
        today_entries = [e for e in series if e["date"] == today]
        assert len(today_entries) == 1
        assert today_entries[0]["expense"] == pytest.approx(200.0)


class TestWeeklySummaryCache:
    def test_cache_miss_header(self, client):
        token = _register_and_login(client, "cache-miss")
        resp = client.get("/dashboard/weekly-summary", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.headers.get("X-Cache") == "MISS"


class TestWeeklySummaryGraphQL:
    _GQL = """
    query WeeklySummary($period: String) {
      weeklySummary(period: $period) {
        period
        seriesStart
        seriesEnd
        currentWeek {
          start
          end
          income
          expense
          balance
          transactionCount
        }
        previousWeek {
          start
          end
          income
          expense
          balance
          transactionCount
        }
        comparison {
          incomeDelta
          incomeDeltaPercent
          expenseDelta
          expenseDeltaPercent
          balanceDelta
          balanceDeltaPercent
        }
        series {
          date
          income
          expense
          balance
        }
      }
    }
    """

    def test_graphql_weekly_summary_shape(self, client):
        token = _register_and_login(client, "gql-shape")
        resp = client.post(
            "/graphql",
            headers=_auth(token),
            json={"query": self._GQL, "variables": {"period": "1m"}},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "errors" not in body, body.get("errors")
        ws = body["data"]["weeklySummary"]
        assert ws["period"] == "1m"
        assert "currentWeek" in ws
        assert "comparison" in ws
        assert isinstance(ws["series"], list)
