"""GraphQL mutations for Budget domain (H-PROD-04 / #886)."""

from __future__ import annotations

from typing import Any, NoReturn
from uuid import UUID

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_FORBIDDEN,
    GRAPHQL_ERROR_CODE_NOT_FOUND,
    GRAPHQL_ERROR_CODE_VALIDATION,
    build_public_graphql_error,
)
from app.graphql.queries.budget import _to_budget_type
from app.graphql.types import BudgetType
from app.services.budget_service import BudgetService, BudgetServiceError

_BUDGET_ERROR_MAP = {
    "NOT_FOUND": GRAPHQL_ERROR_CODE_NOT_FOUND,
    "FORBIDDEN": GRAPHQL_ERROR_CODE_FORBIDDEN,
    "VALIDATION_ERROR": GRAPHQL_ERROR_CODE_VALIDATION,
    "TAG_NOT_FOUND": GRAPHQL_ERROR_CODE_NOT_FOUND,
}


def _raise_budget_graphql_error(exc: BudgetServiceError) -> NoReturn:
    gql_code = _BUDGET_ERROR_MAP.get(exc.code, GRAPHQL_ERROR_CODE_VALIDATION)
    raise build_public_graphql_error(exc.message, code=gql_code)


class CreateBudgetMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        amount = graphene.String(required=True)
        period = graphene.String(required=True)
        tag_id = graphene.String()
        start_date = graphene.String()
        end_date = graphene.String()
        is_active = graphene.Boolean()

    message = graphene.String(required=True)
    budget = graphene.Field(BudgetType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> "CreateBudgetMutation":
        user = get_current_user_required()
        service = BudgetService(UUID(str(user.id)))
        try:
            budget = service.create_budget(kwargs)
        except BudgetServiceError as exc:
            _raise_budget_graphql_error(exc)
        return CreateBudgetMutation(
            message="Orçamento criado com sucesso",
            budget=_to_budget_type(service.serialize_with_spent(budget)),
        )


class UpdateBudgetMutation(graphene.Mutation):
    class Arguments:
        budget_id = graphene.UUID(required=True)
        name = graphene.String()
        amount = graphene.String()
        period = graphene.String()
        tag_id = graphene.String()
        start_date = graphene.String()
        end_date = graphene.String()
        is_active = graphene.Boolean()

    message = graphene.String(required=True)
    budget = graphene.Field(BudgetType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, budget_id: UUID, **kwargs: Any
    ) -> "UpdateBudgetMutation":
        user = get_current_user_required()
        service = BudgetService(UUID(str(user.id)))
        try:
            budget = service.update_budget(budget_id, kwargs)
        except BudgetServiceError as exc:
            _raise_budget_graphql_error(exc)
        return UpdateBudgetMutation(
            message="Orçamento atualizado com sucesso",
            budget=_to_budget_type(service.serialize_with_spent(budget)),
        )


class DeleteBudgetMutation(graphene.Mutation):
    class Arguments:
        budget_id = graphene.UUID(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, budget_id: UUID
    ) -> "DeleteBudgetMutation":
        user = get_current_user_required()
        service = BudgetService(UUID(str(user.id)))
        try:
            service.delete_budget(budget_id)
        except BudgetServiceError as exc:
            _raise_budget_graphql_error(exc)
        return DeleteBudgetMutation(ok=True, message="Orçamento removido com sucesso")
