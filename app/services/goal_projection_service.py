"""Goal Projection Service — portfolio-aware investment projection (H-PROD-02 / #861).

Computes how quickly a user will reach a goal given their current portfolio
return rate, current savings, and planned monthly contribution.

The core difference from the existing ``GoalPlanningService`` is the use of
compound interest (drawn from real wallet ``annual_rate`` data) instead of
the simpler linear accumulation model.

Math:
    With a monthly return rate ``r`` and regular monthly contribution ``C``,
    the future value after ``n`` months is:

        FV = PV * (1+r)^n + C * ((1+r)^n - 1) / r

    Solving for the number of months ``n`` needed to reach ``target``:

        n = log((target + C/r) / (current + C/r)) / log(1+r)

    When ``r == 0`` (no portfolio or zero return), falls back to the linear
    formula: ``n = ceil(remaining / C)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Sequence, cast
from uuid import UUID

from dateutil.relativedelta import relativedelta

from app.models.wallet import Wallet

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MONEY_QUANTIZER = Decimal("0.01")
_RATE_QUANTIZER = Decimal("0.000001")

# Ceiling on the number of projection months to prevent infinite loops.
_MAX_PROJECTION_MONTHS = 1200  # 100 years


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def _format_money(value: Decimal) -> str:
    return f"{_normalize_money(value):.2f}"


def _safe_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


# ---------------------------------------------------------------------------
# Portfolio return calculation
# ---------------------------------------------------------------------------


def _fetch_user_wallets(user_id: UUID) -> Sequence[Wallet]:
    return cast(
        Sequence[Wallet],
        Wallet.query.filter_by(user_id=user_id, should_be_on_wallet=True).all(),
    )


def compute_portfolio_monthly_return_rate(user_id: UUID) -> Decimal:
    """Return the blended monthly return rate from the user's active wallets.

    Computes a value-weighted average of each wallet's ``annual_rate``,
    then converts to a monthly rate: ``(1 + annual_rate) ^ (1/12) - 1``.

    Returns ``Decimal("0")`` when no wallet data is available or when the
    blended annual rate is zero.
    """
    wallets = _fetch_user_wallets(user_id)
    total_value = sum(
        (_safe_decimal(w.value) for w in wallets if w.value is not None),
        Decimal("0"),
    )
    if total_value <= 0:
        return Decimal("0")

    weighted_annual_rate_pct = sum(
        _safe_decimal(w.value) * _safe_decimal(w.annual_rate)
        for w in wallets
        if w.value is not None and w.annual_rate is not None
    )
    blended_annual_rate = weighted_annual_rate_pct / total_value / Decimal("100")

    if blended_annual_rate <= 0:
        return Decimal("0")

    # Convert annual → monthly: (1 + r_annual)^(1/12) - 1
    monthly_rate = Decimal(
        str((1 + float(blended_annual_rate)) ** (1 / 12) - 1)
    ).quantize(_RATE_QUANTIZER, rounding=ROUND_HALF_UP)
    return monthly_rate


# ---------------------------------------------------------------------------
# Projection math
# ---------------------------------------------------------------------------


def _months_to_reach_goal_compound(
    *,
    current: Decimal,
    target: Decimal,
    monthly_contribution: Decimal,
    monthly_rate: Decimal,
) -> int | None:
    """Compound-interest months-to-goal calculation.

    Returns ``None`` when the goal cannot be reached (zero contribution and
    zero return on a positive remaining balance), or ``0`` when already there.
    """
    remaining = target - current
    if remaining <= 0:
        return 0

    r = float(monthly_rate)
    c = float(monthly_contribution)
    pv = float(current)
    fv = float(target)

    if r == 0:
        # Degenerate case: linear
        if c <= 0:
            return None
        return math.ceil(float(remaining) / c)

    if c <= 0 and r <= 0:
        return None

    # Standard compound-with-contribution formula
    # n = log((FV + C/r) / (PV + C/r)) / log(1+r)
    cr = c / r
    numerator = fv + cr
    denominator = pv + cr

    if denominator <= 0 or numerator <= 0:
        return None

    ratio = numerator / denominator
    if ratio <= 1:
        # Contribution alone cannot overcome interest drag — effectively impossible
        # within a reasonable horizon.
        return None

    n = math.log(ratio) / math.log(1 + r)
    months = math.ceil(n)
    if months > _MAX_PROJECTION_MONTHS:
        return None
    return max(months, 0)


def _suggested_monthly_contribution(
    *,
    current: Decimal,
    target: Decimal,
    months_to_deadline: int,
    monthly_rate: Decimal,
) -> Decimal:
    """Return the monthly contribution needed to reach ``target`` in exactly
    ``months_to_deadline`` months given a monthly return rate ``r``.

    Formula (solving for C):
        target = current * (1+r)^n + C * ((1+r)^n - 1) / r

        C = (target - current * (1+r)^n) * r / ((1+r)^n - 1)

    Falls back to simple division when ``r == 0``.
    """
    remaining = target - current
    if remaining <= 0:
        return Decimal("0")
    if months_to_deadline <= 0:
        return remaining

    r = float(monthly_rate)
    n = months_to_deadline

    if r == 0:
        return _normalize_money(remaining / Decimal(n))

    growth = (1 + r) ** n
    numerator = float(target) - float(current) * growth
    denominator = (growth - 1) / r

    if denominator == 0:
        return _normalize_money(remaining / Decimal(n))

    c = numerator / denominator
    return _normalize_money(Decimal(str(max(c, 0.0))))


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoalProjection:
    """Compound-interest projection for a single goal."""

    goal_id: UUID
    current_amount: Decimal
    target_amount: Decimal
    remaining_amount: Decimal
    monthly_contribution: Decimal
    portfolio_monthly_return_rate: Decimal
    portfolio_annual_return_rate_pct: Decimal
    months_to_completion: int | None
    projected_completion_date: date | None
    on_track: bool
    months_until_deadline: int | None
    suggested_monthly_contribution: Decimal | None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GoalProjectionService:
    """Portfolio-aware goal completion projection service.

    Given a goal and a user's wallet portfolio, computes a compound-interest
    projection: how many months until the goal is reached, whether the user
    is on track to meet the deadline, and what monthly contribution would be
    needed to meet it exactly.
    """

    def __init__(
        self,
        *,
        monthly_contribution: Decimal,
        today_provider: Callable[[], date] | None = None,
        portfolio_rate_provider: Callable[[UUID], Decimal] | None = None,
    ) -> None:
        self._monthly_contribution = monthly_contribution
        self._today_provider = today_provider or date.today
        self._portfolio_rate_provider = (
            portfolio_rate_provider or compute_portfolio_monthly_return_rate
        )

    def project(
        self,
        *,
        goal_id: UUID,
        user_id: UUID,
        current_amount: Decimal,
        target_amount: Decimal,
        target_date: date | None,
    ) -> GoalProjection:
        today = self._today_provider()
        monthly_rate = self._portfolio_rate_provider(user_id)
        annual_rate_pct = (
            _normalize_money(
                ((Decimal("1") + monthly_rate) ** 12 - Decimal("1")) * Decimal("100")
            )
            if monthly_rate > 0
            else Decimal("0")
        )

        remaining = max(target_amount - current_amount, Decimal("0"))
        months_to_completion = _months_to_reach_goal_compound(
            current=current_amount,
            target=target_amount,
            monthly_contribution=self._monthly_contribution,
            monthly_rate=monthly_rate,
        )

        projected_completion_date: date | None = None
        if months_to_completion is not None:
            projected_completion_date = today + relativedelta(
                months=months_to_completion
            )

        months_until_deadline: int | None = None
        on_track = False
        if target_date is not None:
            if target_date > today:
                diff = (target_date.year - today.year) * 12 + (
                    target_date.month - today.month
                )
                months_until_deadline = max(diff, 0)
            else:
                months_until_deadline = 0

            if remaining <= 0:
                on_track = True
            elif months_to_completion is not None and months_until_deadline is not None:
                on_track = months_to_completion <= months_until_deadline

        suggested: Decimal | None = None
        if (
            target_date is not None
            and months_until_deadline is not None
            and months_until_deadline > 0
            and not on_track
        ):
            suggested = _suggested_monthly_contribution(
                current=current_amount,
                target=target_amount,
                months_to_deadline=months_until_deadline,
                monthly_rate=monthly_rate,
            )

        return GoalProjection(
            goal_id=goal_id,
            current_amount=_normalize_money(current_amount),
            target_amount=_normalize_money(target_amount),
            remaining_amount=_normalize_money(remaining),
            monthly_contribution=_normalize_money(self._monthly_contribution),
            portfolio_monthly_return_rate=monthly_rate,
            portfolio_annual_return_rate_pct=annual_rate_pct,
            months_to_completion=months_to_completion,
            projected_completion_date=projected_completion_date,
            on_track=on_track,
            months_until_deadline=months_until_deadline,
            suggested_monthly_contribution=suggested,
        )

    def serialize(self, projection: GoalProjection) -> dict[str, object]:
        return {
            "goal_id": str(projection.goal_id),
            "current_amount": _format_money(projection.current_amount),
            "target_amount": _format_money(projection.target_amount),
            "remaining_amount": _format_money(projection.remaining_amount),
            "monthly_contribution": _format_money(projection.monthly_contribution),
            "portfolio_monthly_return_rate": str(
                projection.portfolio_monthly_return_rate
            ),
            "portfolio_annual_return_rate_pct": _format_money(
                projection.portfolio_annual_return_rate_pct
            ),
            "months_to_completion": projection.months_to_completion,
            "projected_completion_date": (
                projection.projected_completion_date.isoformat()
                if projection.projected_completion_date is not None
                else None
            ),
            "on_track": projection.on_track,
            "months_until_deadline": projection.months_until_deadline,
            "suggested_monthly_contribution": (
                _format_money(projection.suggested_monthly_contribution)
                if projection.suggested_monthly_contribution is not None
                else None
            ),
        }
