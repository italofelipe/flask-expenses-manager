"""Unit tests for the deterministic projections block (#1394).

Projections must be computed in the backend (the LLM cannot invent figures —
the evidence validator drops un-anchored numbers). Rate basis: observed wallet
return (weighted), CDI fallback when there are no positions. Horizons: 3/6/12m.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.financial_insight_context_builder import _compute_projections


def _money(value: object) -> Decimal:
    return Decimal(str(value))


def test_wallet_projection_uses_observed_weighted_rate() -> None:
    wallet = {
        "total_value": "1000.00",
        "items": [{"current_value": "1000.00", "annual_rate": "12.00"}],
        "benchmark": {"cdi_monthly_pct": "0.50"},
    }
    proj = _compute_projections(wallet=wallet, goals=[], available_margin=Decimal("0"))

    assert proj["rate_basis"] == "observed"
    assert proj["horizons_months"] == [3, 6, 12]
    # 12% a.a. → after 12 months ≈ 1120 (monthly-compounded back to the annual rate).
    fv12 = _money(proj["wallet"]["horizon_12m"])
    assert abs(fv12 - Decimal("1120.00")) < Decimal("1.00")


def test_wallet_rate_falls_back_to_cdi_without_positions() -> None:
    wallet = {
        "total_value": "0.00",
        "items": [],
        "benchmark": {"cdi_monthly_pct": "1.00"},
    }
    proj = _compute_projections(wallet=wallet, goals=[], available_margin=Decimal("0"))
    assert proj["rate_basis"] == "cdi_fallback"
    # No positions → no wallet projection block.
    assert "wallet" not in proj


def test_goal_projection_observed_and_required() -> None:
    goals = [
        {
            "title": "Viagem",
            "current_amount": "500.00",
            "observed_monthly_pace_90d": "100.00",
            "required_monthly_pace": "200.00",
            "target_date": "2027-05-30",
        }
    ]
    proj = _compute_projections(
        wallet={"total_value": "0.00", "items": [], "benchmark": {}},
        goals=goals,
        available_margin=Decimal("0"),
    )
    g = proj["goals"][0]
    assert _money(g["horizon_12m_observed"]) == Decimal("1700.00")  # 500 + 100*12
    assert _money(g["horizon_12m_required"]) == Decimal("2900.00")  # 500 + 200*12


def test_combined_scenario_uses_required_pace_and_margin() -> None:
    goals = [
        {
            "title": "Viagem",
            "current_amount": "500.00",
            "observed_monthly_pace_90d": "0.00",
            "required_monthly_pace": "200.00",
            "target_date": "2027-05-30",
        }
    ]
    wallet = {
        "total_value": "0.00",
        "items": [],
        "benchmark": {"cdi_monthly_pct": "1.00"},
    }
    proj = _compute_projections(
        wallet=wallet, goals=goals, available_margin=Decimal("300.00")
    )
    combined = proj["combined_scenario"]
    assert _money(combined["monthly_goal_contribution"]) == Decimal("200.00")
    assert _money(combined["monthly_investment"]) == Decimal("300.00")
    # 3m: goal 200*3=600 + annuity FV(300, 1%, 3)=~909 → ~1509
    assert _money(combined["horizon_3m"]) > Decimal("1500.00")


def test_empty_inputs_produce_clean_absence() -> None:
    proj = _compute_projections(
        wallet={"total_value": "0.00", "items": [], "benchmark": {}},
        goals=[],
        available_margin=Decimal("0"),
    )
    assert proj["rate_basis"] == "none"
    assert "wallet" not in proj
    assert "goals" not in proj
    assert "combined_scenario" not in proj
