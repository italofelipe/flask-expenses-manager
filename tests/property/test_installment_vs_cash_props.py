"""Property-based tests for InstallmentVsCashService (#1087).

Uses Hypothesis to verify mathematical invariants that must hold for all
valid inputs.  The service is pure (no DB I/O), so no Flask app context is
needed.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.services.installment_vs_cash_service import InstallmentVsCashService
from app.services.installment_vs_cash_types import InstallmentVsCashCalculationInput

# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

# Positive monetary amounts in BRL: 10.00 – 50 000.00
_money = st.decimals(
    min_value=Decimal("10.00"),
    max_value=Decimal("50000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Installment counts: 2–48 (realistic consumer credit range)
_installment_count = st.integers(min_value=2, max_value=48)

# Annual inflation / opportunity rate: 1.00 – 30.00 %
_annual_rate_pct = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("30.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# First payment delay in days: 0–90
_delay_days = st.integers(min_value=0, max_value=90)


def _build_service() -> InstallmentVsCashService:
    return InstallmentVsCashService(
        default_opportunity_rate_annual_percent=Decimal("13.75"),
    )


@st.composite
def _calculation_input(draw: st.DrawFn) -> InstallmentVsCashCalculationInput:
    """Produce a valid InstallmentVsCashCalculationInput via Hypothesis draw."""
    cash_price = draw(_money)
    installment_count = draw(_installment_count)
    # installment_total >= cash_price (installments are always >= cash price)
    # use a multiplier 1.00 – 1.50 to introduce realistic fees
    multiplier = draw(
        st.decimals(
            min_value=Decimal("1.00"),
            max_value=Decimal("1.50"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    installment_total = (cash_price * multiplier).quantize(Decimal("0.01"))

    inflation_rate = draw(_annual_rate_pct)
    opportunity_rate = draw(_annual_rate_pct)
    first_payment_delay_days = draw(_delay_days)

    payload: InstallmentVsCashCalculationInput = {
        "cash_price": str(cash_price),
        "installment_count": installment_count,
        "installment_total": str(installment_total),
        "inflation_rate_annual": str(inflation_rate),
        "fees_enabled": False,
        "fees_upfront": "0.00",
        "first_payment_delay_days": first_payment_delay_days,
        "opportunity_rate_type": "manual",
        "opportunity_rate_annual": str(opportunity_rate),
        "scenario_label": None,
    }
    return payload


# ---------------------------------------------------------------------------
# Property 1: nominal total conservation
#   inputs.installment_total == sum(schedule[i].amount for all i)
# ---------------------------------------------------------------------------


@given(payload=_calculation_input())
@settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_installment_nominal_total_conservation(
    payload: InstallmentVsCashCalculationInput,
) -> None:
    """Sum of schedule amounts equals the declared installment_total."""
    service = _build_service()
    calc = service.calculate(payload)

    schedule = calc.result["schedule"]
    schedule_sum = sum(Decimal(item["amount"]) for item in schedule)
    declared_total = Decimal(calc.inputs["installment_total"])

    # Allow ±0.02 BRL for rounding distribution across installments
    diff = abs(schedule_sum - declared_total)
    assert diff <= Decimal("0.02"), (
        f"Schedule sum {schedule_sum} deviates from declared total "
        f"{declared_total} by {diff} (threshold 0.02)"
    )


# ---------------------------------------------------------------------------
# Property 2: recommendation is a valid enum value
# ---------------------------------------------------------------------------


@given(payload=_calculation_input())
@settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_recommendation_is_valid_option(
    payload: InstallmentVsCashCalculationInput,
) -> None:
    """recommended_option is always one of the three valid literals."""
    valid_options = {"cash", "installment", "equivalent"}
    service = _build_service()
    calc = service.calculate(payload)

    recommendation = calc.result["recommended_option"]
    assert recommendation in valid_options, (
        f"recommended_option {recommendation!r} is not in {valid_options}"
    )


# ---------------------------------------------------------------------------
# Property 3: present value of installments is always positive
# ---------------------------------------------------------------------------


@given(payload=_calculation_input())
@settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_installment_present_value_is_positive(
    payload: InstallmentVsCashCalculationInput,
) -> None:
    """installment_present_value is always > 0 when inputs are positive."""
    service = _build_service()
    calc = service.calculate(payload)

    pv = Decimal(calc.result["comparison"]["installment_present_value"])
    assert pv > Decimal("0"), f"installment_present_value must be positive, got {pv}"
