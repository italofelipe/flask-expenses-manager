from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.application.services.goal_application_service import (
    GoalApplicationError,
    GoalApplicationService,
)
from app.services.goal_service import GoalServiceError


class _FakeGoal:
    def __init__(self, *, target_amount: str, current_amount: str, target_date: date):
        self.target_amount = Decimal(target_amount)
        self.current_amount = Decimal(current_amount)
        self.target_date = target_date


class _FakeGoalService:
    def __init__(self, user_id):
        self.user_id = user_id
        self.goal = _FakeGoal(
            target_amount="10000.00",
            current_amount="2500.00",
            target_date=date(2027, 12, 31),
        )

    def create_goal(self, payload: dict[str, Any]) -> _FakeGoal:
        if not payload.get("title"):
            raise GoalServiceError(
                message="Dados inválidos para meta.",
                code="VALIDATION_ERROR",
                status_code=400,
            )
        return self.goal

    def list_goals(self, *, page: int, per_page: int, status: str | None):
        if status == "invalid":
            raise GoalServiceError(
                message="Status de meta inválido.",
                code="VALIDATION_ERROR",
                status_code=400,
            )
        return [self.goal], {"total": 1, "page": page, "per_page": per_page, "pages": 1}

    def get_goal(self, goal_id):
        return self.goal

    def update_goal(self, goal_id, payload):
        return self.goal

    def delete_goal(self, goal_id):
        return None

    def serialize(self, goal):
        return {
            "id": str(uuid4()),
            "title": "Reserva",
            "target_amount": "10000.00",
            "current_amount": "2500.00",
            "priority": 2,
            "target_date": "2027-12-31",
            "status": "active",
        }


class _FakePlanningService:
    def build_plan(self, planning_input):
        return planning_input

    def serialize_plan(self, plan):
        return {
            "horizon": "medium_term",
            "remaining_amount": "7500.00",
            "capacity_amount": "2000.00",
            "projected_monthly_contribution": "1000.00",
            "recommended_monthly_contribution": "1200.00",
            "months_to_goal": 8,
            "months_until_target_date": 12,
            "estimated_completion_date": "2026-09-01",
            "target_date": "2027-12-31",
            "goal_health": "on_track",
            "recommendations": [],
        }


class _FakeUser:
    monthly_income = Decimal("8000.00")
    monthly_expenses = Decimal("6000.00")
    monthly_investment = Decimal("1000.00")


def _build_service(get_user_by_id):
    return GoalApplicationService(
        user_id=uuid4(),
        goal_service_factory=_FakeGoalService,
        goal_planning_service_factory=_FakePlanningService,
        get_user_by_id=get_user_by_id,
    )


def test_application_service_returns_goal_plan_payload() -> None:
    service = _build_service(lambda user_id: _FakeUser())
    payload = service.get_goal_plan(uuid4())
    assert "goal" in payload
    assert "goal_plan" in payload
    assert payload["goal_plan"]["goal_health"] == "on_track"


def test_application_service_raises_not_found_when_user_missing() -> None:
    service = _build_service(lambda user_id: None)
    with pytest.raises(GoalApplicationError) as exc_info:
        service.get_goal_plan(uuid4())
    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_application_service_maps_domain_validation_errors() -> None:
    service = _build_service(lambda user_id: _FakeUser())
    with pytest.raises(GoalApplicationError) as exc_info:
        service.create_goal({})
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 400
