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
from app.graphql.types import GoalTypeObject
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


def _raise_mapped_goal_error(exc: GoalServiceError) -> None:
    graphql_code = _GOAL_ERROR_CODE_MAP.get(exc.code, GRAPHQL_ERROR_CODE_VALIDATION)
    raise build_public_graphql_error(exc.message, code=graphql_code) from exc


def _to_goal_type(goal_data: dict[str, Any]) -> GoalTypeObject:
    filtered = {
        key: value for key, value in goal_data.items() if key in _GOAL_GRAPHQL_FIELDS
    }
    return GoalTypeObject(**filtered)


class CreateGoalMutation(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        target_amount = graphene.String(required=True)
        current_amount = graphene.String()
        priority = graphene.Int()
        target_date = graphene.String()
        status = graphene.String()
        description = graphene.String()
        category = graphene.String()

    message = graphene.String(required=True)
    goal = graphene.Field(GoalTypeObject, required=True)

    def mutate(self, info: graphene.ResolveInfo, **kwargs: Any) -> "CreateGoalMutation":
        user = get_current_user_required()
        service = GoalService(UUID(str(user.id)))
        try:
            goal = service.create_goal(kwargs)
        except GoalServiceError as exc:
            _raise_mapped_goal_error(exc)
        return CreateGoalMutation(
            message="Meta criada com sucesso",
            goal=_to_goal_type(service.serialize(goal)),
        )


class UpdateGoalMutation(graphene.Mutation):
    class Arguments:
        goal_id = graphene.UUID(required=True)
        title = graphene.String()
        target_amount = graphene.String()
        current_amount = graphene.String()
        priority = graphene.Int()
        target_date = graphene.String()
        status = graphene.String()
        description = graphene.String()
        category = graphene.String()

    message = graphene.String(required=True)
    goal = graphene.Field(GoalTypeObject, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, goal_id: UUID, **kwargs: Any
    ) -> "UpdateGoalMutation":
        user = get_current_user_required()
        service = GoalService(UUID(str(user.id)))
        try:
            updated = service.update_goal(goal_id, kwargs)
        except GoalServiceError as exc:
            _raise_mapped_goal_error(exc)
        return UpdateGoalMutation(
            message="Meta atualizada com sucesso",
            goal=_to_goal_type(service.serialize(updated)),
        )


class DeleteGoalMutation(graphene.Mutation):
    class Arguments:
        goal_id = graphene.UUID(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(self, info: graphene.ResolveInfo, goal_id: UUID) -> "DeleteGoalMutation":
        user = get_current_user_required()
        service = GoalService(UUID(str(user.id)))
        try:
            service.delete_goal(goal_id)
        except GoalServiceError as exc:
            _raise_mapped_goal_error(exc)
        return DeleteGoalMutation(
            ok=True,
            message="Meta removida com sucesso",
        )
