"""Property-based tests for goal projection math (#1087).

Verifies mathematical invariants in GoalProjectionService and the underlying
compound-interest helpers.  All functions under test are pure (no DB I/O) when
using a mock ``portfolio_rate_provider``.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.services.goal_projection_service import (
    GoalProjectionService,
    _months_to_reach_goal_compound,
    _suggested_monthly_contribution,
)

# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

# Monetary amounts: 100.00 – 100 000.00
_money = st.decimals(
    min_value=Decimal("100.00"),
    max_value=Decimal("100000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Monthly contribution: 50.00 – 5 000.00
_contribution = st.decimals(
    min_value=Decimal("50.00"),
    max_value=Decimal("5000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Monthly return rate: 0.1 % – 2.0 % (realistic for BRL fixed income)
_monthly_rate = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("0.020"),
    places=6,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 1: Monotonicity — higher monthly contribution → fewer months to goal
# ---------------------------------------------------------------------------


@given(
    current=_money,
    additional=_money,
    monthly_rate=_monthly_rate,
    low_contribution=_contribution,
)
@settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_higher_contribution_means_fewer_months(
    current: Decimal,
    additional: Decimal,
    monthly_rate: Decimal,
    low_contribution: Decimal,
) -> None:
    """Doubling the monthly contribution must not increase months-to-goal."""
    # Ensure target > current so there is work to do
    target = current + additional

    high_contribution = low_contribution * Decimal("2")

    months_low = _months_to_reach_goal_compound(
        current=current,
        target=target,
        monthly_contribution=low_contribution,
        monthly_rate=monthly_rate,
    )
    months_high = _months_to_reach_goal_compound(
        current=current,
        target=target,
        monthly_contribution=high_contribution,
        monthly_rate=monthly_rate,
    )

    # Both must be reachable for the monotonicity claim to hold
    if months_low is None or months_high is None:
        return

    assert months_high <= months_low, (
        f"Higher contribution ({high_contribution}) yielded more months "
        f"({months_high}) than lower contribution ({low_contribution}) → "
        f"({months_low}). Monotonicity violation."
    )


# ---------------------------------------------------------------------------
# Property 2: months_to_goal is always >= 1 for valid positive inputs
# ---------------------------------------------------------------------------


@given(
    current=_money,
    additional=_money,
    contribution=_contribution,
    monthly_rate=_monthly_rate,
)
@settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_months_to_goal_at_least_one(
    current: Decimal,
    additional: Decimal,
    contribution: Decimal,
    monthly_rate: Decimal,
) -> None:
    """When target > current and contribution > 0, months_to_goal is ≥ 1."""
    target = current + additional  # always > current

    months = _months_to_reach_goal_compound(
        current=current,
        target=target,
        monthly_contribution=contribution,
        monthly_rate=monthly_rate,
    )

    if months is not None:
        assert months >= 1, (
            f"months_to_goal={months} for current={current}, target={target}, "
            f"contribution={contribution} — must be ≥ 1 when remaining > 0"
        )


# ---------------------------------------------------------------------------
# Property 3: suggested_monthly_contribution is non-negative
# ---------------------------------------------------------------------------


@given(
    current=_money,
    additional=_money,
    months_to_deadline=st.integers(min_value=1, max_value=360),
    monthly_rate=_monthly_rate,
)
@settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_suggested_contribution_non_negative(
    current: Decimal,
    additional: Decimal,
    months_to_deadline: int,
    monthly_rate: Decimal,
) -> None:
    """suggested_monthly_contribution is always ≥ 0 for valid inputs."""
    target = current + additional  # always > current

    suggested = _suggested_monthly_contribution(
        current=current,
        target=target,
        months_to_deadline=months_to_deadline,
        monthly_rate=monthly_rate,
    )

    assert suggested >= Decimal("0"), (
        f"suggested_monthly_contribution={suggested} is negative for "
        f"current={current}, target={target}, months={months_to_deadline}"
    )


# ---------------------------------------------------------------------------
# Property 4: GoalProjectionService.project() returns self-consistent result
#   on_track=True requires months_to_completion <= months_until_deadline
# ---------------------------------------------------------------------------


@given(
    current=_money,
    additional=_money,
    contribution=_contribution,
    monthly_rate=_monthly_rate,
    months_deadline=st.integers(min_value=6, max_value=120),
)
@settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_projection_on_track_consistency(
    current: Decimal,
    additional: Decimal,
    contribution: Decimal,
    monthly_rate: Decimal,
    months_deadline: int,
) -> None:
    """on_track=True implies months_to_completion <= months_until_deadline."""
    target = current + additional
    today = date.today()
    from dateutil.relativedelta import relativedelta

    target_date = today + relativedelta(months=months_deadline)

    service = GoalProjectionService(
        monthly_contribution=contribution,
        today_provider=lambda: today,
        portfolio_rate_provider=lambda uid: monthly_rate,
    )
    projection = service.project(
        goal_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        current_amount=current,
        target_amount=target,
        target_date=target_date,
    )

    if projection.on_track and projection.months_to_completion is not None:
        assert projection.months_until_deadline is not None
        assert projection.months_to_completion <= projection.months_until_deadline, (
            f"on_track=True but months_to_completion "
            f"({projection.months_to_completion}) "
            f"> months_until_deadline ({projection.months_until_deadline})"
        )
