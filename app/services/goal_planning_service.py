from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from math import ceil
from typing import Callable, Protocol

from dateutil.relativedelta import relativedelta

MONEY_QUANTIZER = Decimal("0.01")


def _normalize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def _format_money(value: Decimal) -> str:
    return f"{_normalize_money(value):.2f}"


def _safe_decimal(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _months_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day > start.day:
        months += 1
    return max(months, 0)


class GoalProjectionStrategy(Protocol):
    def months_to_reach_goal(
        self,
        *,
        remaining_amount: Decimal,
        monthly_contribution: Decimal,
    ) -> int | None:
        raise NotImplementedError


class LinearGoalProjectionStrategy:
    def months_to_reach_goal(
        self,
        *,
        remaining_amount: Decimal,
        monthly_contribution: Decimal,
    ) -> int | None:
        if remaining_amount <= 0:
            return 0
        if monthly_contribution <= 0:
            return None
        return int(ceil(float(remaining_amount / monthly_contribution)))


@dataclass(frozen=True)
class GoalPlanningInput:
    target_amount: Decimal
    current_amount: Decimal
    target_date: date | None
    monthly_income: Decimal | None
    monthly_expenses: Decimal | None
    monthly_contribution: Decimal | None


@dataclass(frozen=True)
class GoalRecommendation:
    priority: str
    title: str
    action: str
    estimated_date: date | None = None


@dataclass(frozen=True)
class GoalPlan:
    horizon: str
    remaining_amount: Decimal
    capacity_amount: Decimal
    projected_monthly_contribution: Decimal
    recommended_monthly_contribution: Decimal
    months_to_goal: int | None
    months_until_target_date: int | None
    estimated_completion_date: date | None
    target_date: date | None
    goal_health: str
    recommendations: tuple[GoalRecommendation, ...]


class GoalPlanningService:
    def __init__(
        self,
        *,
        projection_strategy: GoalProjectionStrategy | None = None,
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self._projection_strategy = (
            projection_strategy or LinearGoalProjectionStrategy()
        )
        self._today_provider = today_provider or date.today

    def build_plan(self, planning_input: GoalPlanningInput) -> GoalPlan:
        today = self._today_provider()

        target_amount = _safe_decimal(planning_input.target_amount) or Decimal("0")
        current_amount = _safe_decimal(planning_input.current_amount) or Decimal("0")
        monthly_income = _safe_decimal(planning_input.monthly_income)
        monthly_expenses = _safe_decimal(planning_input.monthly_expenses)
        monthly_contribution = _safe_decimal(planning_input.monthly_contribution)

        remaining_amount = max(target_amount - current_amount, Decimal("0"))
        capacity_amount = self._resolve_capacity(monthly_income, monthly_expenses)
        projected_contribution = self._resolve_projected_contribution(
            monthly_contribution=monthly_contribution,
            capacity_amount=capacity_amount,
            remaining_amount=remaining_amount,
        )

        months_until_target_date = (
            _months_between(today, planning_input.target_date)
            if planning_input.target_date is not None
            else None
        )
        recommended_monthly_contribution = self._resolve_recommended_contribution(
            remaining_amount=remaining_amount,
            projected_contribution=projected_contribution,
            months_until_target_date=months_until_target_date,
        )
        months_to_goal = self._projection_strategy.months_to_reach_goal(
            remaining_amount=remaining_amount,
            monthly_contribution=projected_contribution,
        )
        estimated_completion_date = self._resolve_estimated_date(
            today=today,
            months_to_goal=months_to_goal,
        )
        horizon = self._resolve_horizon(months_to_goal, months_until_target_date)
        goal_health = self._resolve_goal_health(
            remaining_amount=remaining_amount,
            months_to_goal=months_to_goal,
            months_until_target_date=months_until_target_date,
        )
        recommendations = self._build_recommendations(
            today=today,
            remaining_amount=remaining_amount,
            capacity_amount=capacity_amount,
            projected_contribution=projected_contribution,
            recommended_contribution=recommended_monthly_contribution,
            months_to_goal=months_to_goal,
            months_until_target_date=months_until_target_date,
            estimated_completion_date=estimated_completion_date,
        )

        return GoalPlan(
            horizon=horizon,
            remaining_amount=_normalize_money(remaining_amount),
            capacity_amount=_normalize_money(capacity_amount),
            projected_monthly_contribution=_normalize_money(projected_contribution),
            recommended_monthly_contribution=_normalize_money(
                recommended_monthly_contribution
            ),
            months_to_goal=months_to_goal,
            months_until_target_date=months_until_target_date,
            estimated_completion_date=estimated_completion_date,
            target_date=planning_input.target_date,
            goal_health=goal_health,
            recommendations=tuple(recommendations),
        )

    @staticmethod
    def _resolve_capacity(
        monthly_income: Decimal | None,
        monthly_expenses: Decimal | None,
    ) -> Decimal:
        if monthly_income is None or monthly_expenses is None:
            return Decimal("0")
        return max(monthly_income - monthly_expenses, Decimal("0"))

    @staticmethod
    def _resolve_projected_contribution(
        *,
        monthly_contribution: Decimal | None,
        capacity_amount: Decimal,
        remaining_amount: Decimal,
    ) -> Decimal:
        if monthly_contribution is not None and monthly_contribution > 0:
            return monthly_contribution
        if remaining_amount <= 0:
            return Decimal("0")
        if capacity_amount <= 0:
            return Decimal("0")
        return min(capacity_amount, remaining_amount)

    @staticmethod
    def _resolve_recommended_contribution(
        *,
        remaining_amount: Decimal,
        projected_contribution: Decimal,
        months_until_target_date: int | None,
    ) -> Decimal:
        if remaining_amount <= 0:
            return Decimal("0")
        if months_until_target_date is not None and months_until_target_date > 0:
            required = remaining_amount / Decimal(months_until_target_date)
            return max(required, projected_contribution)
        return projected_contribution

    @staticmethod
    def _resolve_estimated_date(
        *,
        today: date,
        months_to_goal: int | None,
    ) -> date | None:
        if months_to_goal is None:
            return None
        return today + relativedelta(months=months_to_goal)

    @staticmethod
    def _resolve_horizon(
        months_to_goal: int | None,
        months_until_target_date: int | None,
    ) -> str:
        horizon_reference = months_to_goal
        if horizon_reference is None:
            horizon_reference = months_until_target_date
        if horizon_reference is None:
            return "long_term"
        if horizon_reference <= 12:
            return "short_term"
        if horizon_reference <= 36:
            return "medium_term"
        return "long_term"

    @staticmethod
    def _resolve_goal_health(
        *,
        remaining_amount: Decimal,
        months_to_goal: int | None,
        months_until_target_date: int | None,
    ) -> str:
        if remaining_amount <= 0:
            return "completed"
        if months_to_goal is None:
            return "at_risk"
        if months_until_target_date is None:
            return "on_track"
        if months_to_goal <= months_until_target_date:
            return "on_track"
        return "off_track"

    @staticmethod
    def _build_recommendations(
        *,
        today: date,
        remaining_amount: Decimal,
        capacity_amount: Decimal,
        projected_contribution: Decimal,
        recommended_contribution: Decimal,
        months_to_goal: int | None,
        months_until_target_date: int | None,
        estimated_completion_date: date | None,
    ) -> list[GoalRecommendation]:
        if remaining_amount <= 0:
            return [
                GoalRecommendation(
                    priority="low",
                    title="Meta concluída",
                    action="Meta já atingida. Revise e defina um novo objetivo.",
                    estimated_date=today,
                )
            ]

        recommendations: list[GoalRecommendation] = []
        if projected_contribution <= 0:
            recommendations.append(
                GoalRecommendation(
                    priority="high",
                    title="Defina aporte mensal",
                    action=(
                        "Não há aporte mensal viável para avançar na meta. "
                        "Defina um valor recorrente para iniciar a execução."
                    ),
                )
            )

        if capacity_amount <= 0:
            recommendations.append(
                GoalRecommendation(
                    priority="high",
                    title="Recupere capacidade de aporte",
                    action=(
                        "Sua capacidade mensal está zerada. Ajuste despesas ou "
                        "aumente renda para sustentar a meta."
                    ),
                )
            )

        if recommended_contribution > projected_contribution:
            contribution_gap = _normalize_money(
                recommended_contribution - projected_contribution
            )
            recommendations.append(
                GoalRecommendation(
                    priority="high",
                    title="Aumente o aporte para cumprir o prazo",
                    action=(
                        "Para cumprir o prazo da meta, aumente o aporte mensal em "
                        f"R$ {_format_money(contribution_gap)}."
                    ),
                    estimated_date=estimated_completion_date,
                )
            )

        if (
            months_until_target_date is not None
            and months_to_goal is not None
            and months_to_goal > months_until_target_date
        ):
            recommendations.append(
                GoalRecommendation(
                    priority="medium",
                    title="Replaneje o prazo",
                    action=(
                        "No ritmo atual, a data alvo será ultrapassada. "
                        "Replaneje o prazo ou priorize essa meta no orçamento."
                    ),
                    estimated_date=estimated_completion_date,
                )
            )

        if not recommendations:
            recommendations.append(
                GoalRecommendation(
                    priority="low",
                    title="Plano consistente",
                    action=(
                        "A meta está em trajetória saudável. Mantenha o aporte e "
                        "revise o progresso mensalmente."
                    ),
                    estimated_date=estimated_completion_date,
                )
            )
        return recommendations

    def serialize_plan(self, plan: GoalPlan) -> dict[str, object]:
        return {
            "horizon": plan.horizon,
            "remaining_amount": _format_money(plan.remaining_amount),
            "capacity_amount": _format_money(plan.capacity_amount),
            "projected_monthly_contribution": _format_money(
                plan.projected_monthly_contribution
            ),
            "recommended_monthly_contribution": _format_money(
                plan.recommended_monthly_contribution
            ),
            "months_to_goal": plan.months_to_goal,
            "months_until_target_date": plan.months_until_target_date,
            "estimated_completion_date": (
                plan.estimated_completion_date.isoformat()
                if plan.estimated_completion_date
                else None
            ),
            "target_date": plan.target_date.isoformat() if plan.target_date else None,
            "goal_health": plan.goal_health,
            "recommendations": [
                {
                    "priority": item.priority,
                    "title": item.title,
                    "action": item.action,
                    "estimated_date": (
                        item.estimated_date.isoformat()
                        if item.estimated_date is not None
                        else None
                    ),
                }
                for item in plan.recommendations
            ],
        }
