"""Tests for wallet insights pipeline (issue #1243).

Three layers:
- MarketRatesProvider (BCB SGS adapter + Stub + graceful failure)
- investor_profile_targets.evaluate_allocation
- FinancialInsightContextBuilder wallet section (monthly + weekly)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

from app.extensions.database import db
from app.models.wallet import Wallet
from app.services.financial_insight_context_builder import (
    FinancialInsightContextBuilder,
)
from app.services.investor_profile_targets import (
    PROFILE_TARGETS,
    compute_distribution,
    evaluate_allocation,
)
from app.services.market_rates_provider import (
    StubMarketRatesProvider,
    _parse_sgs_payload,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _register(client) -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    email = f"wallet-{suffix}@email.com"
    password = "StrongPass@123"
    register = client.post(
        "/auth/register",
        json={"name": f"u-{suffix}", "email": email, "password": password},
    )
    assert register.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.get_json()["token"]
    from flask_jwt_extended import decode_token

    return token, str(decode_token(token)["sub"])


def _add_wallet(
    app,
    *,
    user_id: str,
    name: str,
    asset_class: str,
    value: str,
    annual_rate: str | None = None,
    ticker: str | None = None,
) -> None:
    with app.app_context():
        w = Wallet(
            user_id=UUID(user_id),
            name=name,
            asset_class=asset_class,
            value=Decimal(value),
            annual_rate=Decimal(annual_rate) if annual_rate else None,
            ticker=ticker,
            register_date=date.today(),
            should_be_on_wallet=True,
        )
        db.session.add(w)
        db.session.commit()


# ──────────────────────────────────────────────────────────────────────────────
# MarketRatesProvider
# ──────────────────────────────────────────────────────────────────────────────


class TestStubMarketRatesProvider:
    def test_returns_configured_decimal(self) -> None:
        p = StubMarketRatesProvider(cdi=Decimal("0.92"), ipca=Decimal("0.45"))
        assert p.cdi_monthly(year=2026, month=5) == Decimal("0.92")
        assert p.ipca_monthly(year=2026, month=5) == Decimal("0.45")

    def test_falls_back_to_env_when_not_configured(self, monkeypatch) -> None:
        p = StubMarketRatesProvider()
        monkeypatch.setenv("AI_MARKET_RATE_CDI_MONTHLY", "0.80")
        monkeypatch.setenv("AI_MARKET_RATE_IPCA_MONTHLY", "0.30")
        assert p.cdi_monthly(year=2026, month=5) == Decimal("0.80")
        assert p.ipca_monthly(year=2026, month=5) == Decimal("0.30")

    def test_returns_none_when_neither_configured(self, monkeypatch) -> None:
        p = StubMarketRatesProvider()
        monkeypatch.delenv("AI_MARKET_RATE_CDI_MONTHLY", raising=False)
        monkeypatch.delenv("AI_MARKET_RATE_IPCA_MONTHLY", raising=False)
        assert p.cdi_monthly(year=2026, month=5) is None
        assert p.ipca_monthly(year=2026, month=5) is None


class TestSgsPayloadParser:
    def test_parses_target_month_entry(self) -> None:
        payload = [
            {"data": "30/04/2026", "valor": "0.90"},
            {"data": "31/05/2026", "valor": "0.92"},
        ]
        value = _parse_sgs_payload(payload, target_year=2026, target_month=5)
        assert value == Decimal("0.92")

    def test_returns_none_when_target_absent(self) -> None:
        payload = [{"data": "30/04/2026", "valor": "0.90"}]
        assert _parse_sgs_payload(payload, target_year=2026, target_month=5) is None

    def test_returns_none_for_malformed_payload(self) -> None:
        assert (
            _parse_sgs_payload({"not": "a list"}, target_year=2026, target_month=5)
            is None
        )
        assert _parse_sgs_payload([{}], target_year=2026, target_month=5) is None

    def test_handles_comma_decimal_format(self) -> None:
        payload = [{"data": "31/05/2026", "valor": "0,92"}]
        value = _parse_sgs_payload(payload, target_year=2026, target_month=5)
        assert value == Decimal("0.92")


# ──────────────────────────────────────────────────────────────────────────────
# Investor profile evaluation
# ──────────────────────────────────────────────────────────────────────────────


class _FakeWallet:
    """Lightweight Wallet stand-in for unit tests (no DB)."""

    def __init__(self, asset_class: str, value: str) -> None:
        self.asset_class = asset_class
        self.value = Decimal(value)


class TestEvaluateAllocation:
    def test_aligned_conservador(self) -> None:
        wallets = [
            _FakeWallet("cdb", "7000"),  # 70% RF
            _FakeWallet("stock", "3000"),  # 30% RV
        ]
        diag = evaluate_allocation(investor_profile="conservador", wallets=wallets)
        assert diag.profile == "conservador"
        assert diag.alert_level == "aligned"
        assert diag.distribution.fixed_income_pct == Decimal("70.00")
        assert diag.distribution.market_pct == Decimal("30.00")
        assert diag.drift_pp == Decimal("0.00")

    def test_drift_warn_when_outside_tolerance(self) -> None:
        # 50/50 actual but profile conservador (target 70/30, tolerance ±10pp).
        wallets = [
            _FakeWallet("cdb", "5000"),
            _FakeWallet("stock", "5000"),
        ]
        diag = evaluate_allocation(investor_profile="conservador", wallets=wallets)
        assert diag.alert_level in {"drift_warn", "drift_critical"}
        assert diag.drift_pp == Decimal("20.00")

    def test_unknown_profile_still_returns_distribution(self) -> None:
        wallets = [_FakeWallet("cdb", "1000")]
        diag = evaluate_allocation(investor_profile="exotic", wallets=wallets)
        assert diag.profile is None
        assert diag.target is None
        assert diag.distribution.fixed_income_pct == Decimal("100.00")
        assert "fora do conjunto canônico" in diag.notes[0]

    def test_empty_wallets_returns_zero_distribution(self) -> None:
        diag = evaluate_allocation(investor_profile="moderado", wallets=[])
        assert diag.distribution.total_value == Decimal("0")
        assert diag.distribution.fixed_income_pct == Decimal("0")

    def test_compute_distribution_buckets_custom(self) -> None:
        wallets = [
            _FakeWallet("cdb", "1000"),
            _FakeWallet("stock", "1000"),
            _FakeWallet("custom", "1000"),
        ]
        dist = compute_distribution(wallets)
        assert dist.custom_pct == Decimal("33.33")

    def test_profile_targets_complete(self) -> None:
        assert set(PROFILE_TARGETS) == {"conservador", "moderado", "agressivo"}


# ──────────────────────────────────────────────────────────────────────────────
# FinancialInsightContextBuilder wallet section
# ──────────────────────────────────────────────────────────────────────────────


class TestWalletSnapshotSection:
    def test_monthly_includes_wallet_section(self, app, client) -> None:
        _, user_id = _register(client)
        _add_wallet(
            app,
            user_id=user_id,
            name="CDB Nubank",
            asset_class="cdb",
            value="5000.00",
            annual_rate="13.50",
        )
        _add_wallet(
            app,
            user_id=user_id,
            name="ITSA4",
            asset_class="stock",
            value="2000.00",
            ticker="ITSA4",
        )

        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_monthly(
                user_id=UUID(user_id),
                anchor_date=date(2026, 5, 17),
            )

        assert "wallet" in snapshot
        wallet = snapshot["wallet"]
        assert wallet["items"], "wallet.items must be populated"
        assert Decimal(wallet["total_value"]) == Decimal("7000.00")
        # Sensitive PII must not appear.
        for item in wallet["items"]:
            assert "user_id" not in item
        assert wallet["distribution"]["fixed_income_pct"] is not None
        assert wallet["distribution"]["market_pct"] is not None
        # benchmark block present (may have None values when provider stub returns None)
        assert "benchmark" in wallet

    def test_weekly_also_includes_wallet_section(self, app, client) -> None:
        _, user_id = _register(client)
        _add_wallet(
            app,
            user_id=user_id,
            name="Tesouro Selic",
            asset_class="tesouro",
            value="3000.00",
            annual_rate="13.00",
        )
        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_weekly(
                user_id=UUID(user_id),
                anchor_date=date(2026, 5, 17),
            )
        assert "wallet" in snapshot
        assert snapshot["wallet"]["items"]

    def test_user_without_wallets_returns_empty_list(self, app, client) -> None:
        _, user_id = _register(client)
        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_monthly(
                user_id=UUID(user_id),
                anchor_date=date(2026, 5, 17),
            )
        assert snapshot["wallet"]["items"] == []
        assert Decimal(snapshot["wallet"]["total_value"]) == Decimal("0")

    def test_wallet_section_uses_market_rates_provider_with_fallback(
        self, app, client
    ) -> None:
        _, user_id = _register(client)
        _add_wallet(
            app,
            user_id=user_id,
            name="CDB",
            asset_class="cdb",
            value="1000.00",
        )

        # Patch the provider to return None for both rates → benchmark None +
        # data_quality flag set.
        with patch(
            "app.services.financial_insight_context_builder."
            "get_default_market_rates_provider"
        ) as get_provider:
            stub = StubMarketRatesProvider(cdi=None, ipca=None)
            get_provider.return_value = stub
            with app.app_context():
                snapshot = FinancialInsightContextBuilder().build_monthly(
                    user_id=UUID(user_id),
                    anchor_date=date(2026, 5, 17),
                )
        assert snapshot["wallet"]["benchmark"]["cdi_monthly_pct"] is None
        assert snapshot["wallet"]["benchmark"]["ipca_monthly_pct"] is None
        missing = snapshot["data_quality"].get("missing_external_rates", [])
        assert "cdi_monthly" in missing
        assert "ipca_monthly" in missing

    def test_wallet_section_with_configured_rates(self, app, client) -> None:
        _, user_id = _register(client)
        _add_wallet(
            app,
            user_id=user_id,
            name="CDB",
            asset_class="cdb",
            value="1000.00",
        )
        with patch(
            "app.services.financial_insight_context_builder."
            "get_default_market_rates_provider"
        ) as get_provider:
            stub = StubMarketRatesProvider(cdi=Decimal("0.92"), ipca=Decimal("0.45"))
            get_provider.return_value = stub
            with app.app_context():
                snapshot = FinancialInsightContextBuilder().build_monthly(
                    user_id=UUID(user_id),
                    anchor_date=date(2026, 5, 17),
                )
        assert snapshot["wallet"]["benchmark"]["cdi_monthly_pct"] == "0.92"
        assert snapshot["wallet"]["benchmark"]["ipca_monthly_pct"] == "0.45"

    def test_daily_snapshot_does_not_include_wallet(self, app, client) -> None:
        _, user_id = _register(client)
        _add_wallet(
            app,
            user_id=user_id,
            name="CDB",
            asset_class="cdb",
            value="1000.00",
        )
        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=UUID(user_id),
                anchor_date=date(2026, 5, 17),
            )
        # Wallet is intentionally weekly+monthly only.
        assert snapshot.get("wallet", {}).get("items", []) == []
