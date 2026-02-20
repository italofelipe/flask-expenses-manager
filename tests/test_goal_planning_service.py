from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.goal_planning_service import GoalPlanningInput, GoalPlanningService


def _service_with_fixed_today() -> GoalPlanningService:
    return GoalPlanningService(today_provider=lambda: date(2026, 1, 1))


def test_goal_planning_service_marks_goal_on_track() -> None:
    service = _service_with_fixed_today()
    plan = service.build_plan(
        GoalPlanningInput(
            target_amount=Decimal("24000"),
            current_amount=Decimal("6000"),
            target_date=date(2027, 1, 1),
            monthly_income=Decimal("8000"),
            monthly_expenses=Decimal("5000"),
            monthly_contribution=Decimal("2000"),
        )
    )

    serialized = service.serialize_plan(plan)
    assert serialized["goal_health"] == "on_track"
    assert serialized["months_to_goal"] is not None
    assert serialized["recommended_monthly_contribution"] == "2000.00"
    assert isinstance(serialized["recommendations"], list)
    assert serialized["recommendations"]


def test_goal_planning_service_marks_goal_at_risk_without_contribution() -> None:
    service = _service_with_fixed_today()
    plan = service.build_plan(
        GoalPlanningInput(
            target_amount=Decimal("10000"),
            current_amount=Decimal("1000"),
            target_date=date(2026, 12, 31),
            monthly_income=Decimal("4500"),
            monthly_expenses=Decimal("4500"),
            monthly_contribution=Decimal("0"),
        )
    )

    serialized = service.serialize_plan(plan)
    assert serialized["goal_health"] in {"at_risk", "off_track"}
    assert serialized["months_to_goal"] is None
    assert any(
        recommendation["priority"] == "high"
        for recommendation in serialized["recommendations"]
    )


def test_goal_planning_service_marks_goal_completed() -> None:
    service = _service_with_fixed_today()
    plan = service.build_plan(
        GoalPlanningInput(
            target_amount=Decimal("5000"),
            current_amount=Decimal("5000"),
            target_date=None,
            monthly_income=Decimal("0"),
            monthly_expenses=Decimal("0"),
            monthly_contribution=Decimal("0"),
        )
    )

    serialized = service.serialize_plan(plan)
    assert serialized["goal_health"] == "completed"
    assert serialized["remaining_amount"] == "0.00"
    assert serialized["months_to_goal"] == 0
