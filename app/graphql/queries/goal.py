from __future__ import annotations

from typing import Any
from uuid import UUID

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_FORBIDDEN,
    GRAPHQL_ERROR_CODE_NOT_FOUND,
    GRAPHQL_ERROR_CODE_VALIDATION,
    build_public_graphql_error,
)
from app.graphql.queries.common import paginate
from app.graphql.types import GoalListPayloadType, GoalTypeObject
from app.services.goal_service import GoalService, GoalServiceError

_GOAL_ERROR_CODE_MAP = {
    "VALIDATION_ERROR": GRAPHQL_ERROR_CODE_VALIDATION,
    "NOT_FOUND": GRAPHQL_ERROR_CODE_NOT_FOUND,
    "FORBIDDEN": GRAPHQL_ERROR_CODE_FORBIDDEN,
}
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


def _to_goal_type(goal_data: dict[str, Any]) -> GoalTypeObject:
    filtered = {
        key: value for key, value in goal_data.items() if key in _GOAL_GRAPHQL_FIELDS
    }
    return GoalTypeObject(**filtered)


def _raise_mapped_goal_error(exc: GoalServiceError) -> None:
    graphql_code = _GOAL_ERROR_CODE_MAP.get(exc.code, GRAPHQL_ERROR_CODE_VALIDATION)
    raise build_public_graphql_error(exc.message, code=graphql_code) from exc


class GoalQueryMixin:
    goals = graphene.Field(
        GoalListPayloadType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
        status=graphene.String(),
    )
    goal = graphene.Field(
        GoalTypeObject,
        goal_id=graphene.UUID(required=True),
    )

    def resolve_goals(
        self,
        info: graphene.ResolveInfo,
        page: int,
        per_page: int,
        status: str | None = None,
    ) -> GoalListPayloadType:
        user = get_current_user_required()
        service = GoalService(UUID(str(user.id)))
        try:
            goals, pagination_meta = service.list_goals(
                page=page,
                per_page=per_page,
                status=status,
            )
        except GoalServiceError as exc:
            _raise_mapped_goal_error(exc)

        items = [_to_goal_type(service.serialize(goal)) for goal in goals]
        return GoalListPayloadType(
            items=items,
            pagination=paginate(
                total=pagination_meta["total"],
                page=pagination_meta["page"],
                per_page=pagination_meta["per_page"],
            ),
        )

    def resolve_goal(
        self,
        info: graphene.ResolveInfo,
        goal_id: UUID,
    ) -> GoalTypeObject:
        user = get_current_user_required()
        service = GoalService(UUID(str(user.id)))
        try:
            goal = service.get_goal(goal_id)
        except GoalServiceError as exc:
            _raise_mapped_goal_error(exc)
        return _to_goal_type(service.serialize(goal))
