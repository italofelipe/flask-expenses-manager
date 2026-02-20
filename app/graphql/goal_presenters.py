from __future__ import annotations

from typing import Any

from app.application.services.goal_application_service import GoalApplicationError
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_FORBIDDEN,
    GRAPHQL_ERROR_CODE_NOT_FOUND,
    GRAPHQL_ERROR_CODE_VALIDATION,
    build_public_graphql_error,
)
from app.graphql.types import GoalPlanType, GoalRecommendationType, GoalTypeObject

_GOAL_GRAPHQL_FIELDS = {
    "id",
    "title",
    "description",
    "category",
    "target_amount",
    "current_amount",
    "priority",
    "target_date",
    "status",
    "created_at",
    "updated_at",
}
_GOAL_ERROR_CODE_MAP = {
    "VALIDATION_ERROR": GRAPHQL_ERROR_CODE_VALIDATION,
    "NOT_FOUND": GRAPHQL_ERROR_CODE_NOT_FOUND,
    "FORBIDDEN": GRAPHQL_ERROR_CODE_FORBIDDEN,
}


def raise_goal_graphql_error(exc: GoalApplicationError) -> None:
    graphql_code = _GOAL_ERROR_CODE_MAP.get(exc.code, GRAPHQL_ERROR_CODE_VALIDATION)
    raise build_public_graphql_error(exc.message, code=graphql_code) from exc


def to_goal_type_object(goal_data: dict[str, Any]) -> GoalTypeObject:
    filtered = {
        key: value for key, value in goal_data.items() if key in _GOAL_GRAPHQL_FIELDS
    }
    return GoalTypeObject(**filtered)


def to_goal_plan_type(plan_data: dict[str, Any]) -> GoalPlanType:
    recommendations = [
        GoalRecommendationType(**item)
        for item in plan_data.get("recommendations", [])
        if isinstance(item, dict)
    ]
    payload = dict(plan_data)
    payload["recommendations"] = recommendations
    return GoalPlanType(**payload)
