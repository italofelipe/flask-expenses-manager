from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, cast
from uuid import UUID

from marshmallow import ValidationError

from app.models.user import User
from app.schemas.goal_planning_schema import GoalSimulationSchema
from app.services.goal_planning_service import GoalPlanningInput, GoalPlanningService
from app.services.goal_service import GoalService, GoalServiceError


@dataclass(frozen=True)
class GoalApplicationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None


class GoalApplicationService:
    def __init__(
        self,
        *,
        user_id: UUID,
        goal_service_factory: Callable[[UUID], GoalService],
        goal_planning_service_factory: Callable[[], GoalPlanningService],
        get_user_by_id: Callable[[UUID], User | None],
    ) -> None:
        self._user_id = user_id
        self._goal_service = goal_service_factory(user_id)
        self._goal_planning_service_factory = goal_planning_service_factory
        self._get_user_by_id = get_user_by_id
        self._simulation_schema = GoalSimulationSchema()

    @classmethod
    def with_defaults(cls, user_id: UUID) -> GoalApplicationService:
        return cls(
            user_id=user_id,
            goal_service_factory=GoalService,
            goal_planning_service_factory=GoalPlanningService,
            get_user_by_id=_default_get_user_by_id,
        )

    def create_goal(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            goal = self._goal_service.create_goal(payload)
        except GoalServiceError as exc:
            raise _to_goal_application_error(exc) from exc
        return self._goal_service.serialize(goal)

    def list_goals(
        self,
        *,
        page: int,
        per_page: int,
        status: str | None,
    ) -> dict[str, Any]:
        try:
            goals, pagination = self._goal_service.list_goals(
                page=page,
                per_page=per_page,
                status=status,
            )
        except GoalServiceError as exc:
            raise _to_goal_application_error(exc) from exc
        return {
            "items": [self._goal_service.serialize(goal) for goal in goals],
            "pagination": pagination,
        }

    def get_goal(self, goal_id: UUID) -> dict[str, Any]:
        try:
            goal = self._goal_service.get_goal(goal_id)
        except GoalServiceError as exc:
            raise _to_goal_application_error(exc) from exc
        return self._goal_service.serialize(goal)

    def update_goal(self, goal_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            goal = self._goal_service.update_goal(goal_id, payload)
        except GoalServiceError as exc:
            raise _to_goal_application_error(exc) from exc
        return self._goal_service.serialize(goal)

    def delete_goal(self, goal_id: UUID) -> None:
        try:
            self._goal_service.delete_goal(goal_id)
        except GoalServiceError as exc:
            raise _to_goal_application_error(exc) from exc

    def get_goal_plan(self, goal_id: UUID) -> dict[str, Any]:
        try:
            goal = self._goal_service.get_goal(goal_id)
        except GoalServiceError as exc:
            raise _to_goal_application_error(exc) from exc

        user = self._get_user_by_id(self._user_id)
        if user is None:
            raise GoalApplicationError(
                message="Usuário não encontrado.",
                code="NOT_FOUND",
                status_code=404,
            )

        planning_service = self._goal_planning_service_factory()
        planning_input = GoalPlanningInput(
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            monthly_income=user.monthly_income,
            monthly_expenses=user.monthly_expenses,
            monthly_contribution=user.monthly_investment,
        )
        return {
            "goal": self._goal_service.serialize(goal),
            "goal_plan": planning_service.serialize_plan(
                planning_service.build_plan(planning_input)
            ),
        }

    def simulate_goal_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = self._simulation_schema.load(payload)
        except ValidationError as exc:
            raise GoalApplicationError(
                message="Dados inválidos para simulação de meta.",
                code="VALIDATION_ERROR",
                status_code=400,
                details={"messages": exc.messages},
            ) from exc

        planning_service = self._goal_planning_service_factory()
        planning_input = GoalPlanningInput(
            target_amount=validated["target_amount"],
            current_amount=validated["current_amount"],
            target_date=validated.get("target_date"),
            monthly_income=validated.get("monthly_income"),
            monthly_expenses=validated.get("monthly_expenses"),
            monthly_contribution=validated.get("monthly_contribution"),
        )
        return {
            "goal_plan": planning_service.serialize_plan(
                planning_service.build_plan(planning_input)
            )
        }


def _to_goal_application_error(exc: GoalServiceError) -> GoalApplicationError:
    return GoalApplicationError(
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
    )


def _default_get_user_by_id(user_id: UUID) -> User | None:
    return cast(User | None, User.query.filter_by(id=user_id).first())
