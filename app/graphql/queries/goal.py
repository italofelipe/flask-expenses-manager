from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import graphene

from app.application.services.goal_application_service import (
    GoalApplicationError,
    GoalApplicationService,
)
from app.graphql.auth import get_current_user_required
from app.graphql.goal_presenters import (
    raise_goal_graphql_error,
    to_goal_plan_type,
    to_goal_type_object,
)
from app.graphql.queries.common import paginate
from app.graphql.types import GoalListPayloadType, GoalPlanType, GoalTypeObject


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
    goal_plan = graphene.Field(
        GoalPlanType,
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
        service = GoalApplicationService.with_defaults(UUID(str(user.id)))
        try:
            result = service.list_goals(
                page=page,
                per_page=per_page,
                status=status,
            )
        except GoalApplicationError as exc:
            raise_goal_graphql_error(exc)

        items = [to_goal_type_object(item) for item in result["items"]]
        pagination_meta = result["pagination"]
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
        service = GoalApplicationService.with_defaults(UUID(str(user.id)))
        try:
            goal_data = service.get_goal(goal_id)
        except GoalApplicationError as exc:
            raise_goal_graphql_error(exc)
        return to_goal_type_object(goal_data)

    def resolve_goal_plan(
        self,
        info: graphene.ResolveInfo,
        goal_id: UUID,
    ) -> GoalPlanType:
        user = get_current_user_required()
        service = GoalApplicationService.with_defaults(UUID(str(user.id)))
        try:
            result = service.get_goal_plan(goal_id)
        except GoalApplicationError as exc:
            raise_goal_graphql_error(exc)
        return to_goal_plan_type(cast(dict[str, Any], result["goal_plan"]))
