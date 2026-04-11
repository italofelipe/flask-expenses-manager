"""GraphQL queries for Budget domain (H-PROD-04 / #886).

Mirrors REST endpoints:
  GET /budgets         → budgets
  GET /budgets/<id>    → budget(budgetId)
  GET /budgets/summary → budgetSummary
"""

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
from app.graphql.types import BudgetListPayloadType, BudgetSummaryType, BudgetType
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


def _to_budget_type(data: dict[str, Any]) -> BudgetType:
    return BudgetType(
        id=data["id"],
        name=data["name"],
        amount=data["amount"],
        period=data["period"],
        tag_id=data.get("tag_id"),
        tag_name=data.get("tag_name"),
        tag_color=data.get("tag_color"),
        start_date=str(data["start_date"]) if data.get("start_date") else None,
        end_date=str(data["end_date"]) if data.get("end_date") else None,
        is_active=data["is_active"],
        spent=data["spent"],
        remaining=data["remaining"],
        percentage_used=data["percentage_used"],
        is_over_budget=data["is_over_budget"],
        created_at=str(data["created_at"]) if data.get("created_at") else None,
        updated_at=str(data["updated_at"]) if data.get("updated_at") else None,
    )


class BudgetQueryMixin:
    budgets = graphene.Field(BudgetListPayloadType)
    budget = graphene.Field(
        BudgetType,
        budget_id=graphene.UUID(required=True),
    )
    budget_summary = graphene.Field(BudgetSummaryType)

    def resolve_budgets(self, _info: graphene.ResolveInfo) -> BudgetListPayloadType:
        user = get_current_user_required()
        service = BudgetService(UUID(str(user.id)))
        budgets = service.list_budgets()
        items = [_to_budget_type(service.serialize_with_spent(b)) for b in budgets]
        return BudgetListPayloadType(items=items)

    def resolve_budget(
        self,
        _info: graphene.ResolveInfo,
        budget_id: UUID,
    ) -> BudgetType:
        user = get_current_user_required()
        service = BudgetService(UUID(str(user.id)))
        try:
            budget = service.get_budget(budget_id)
        except BudgetServiceError as exc:
            _raise_budget_graphql_error(exc)
        return _to_budget_type(service.serialize_with_spent(budget))

    def resolve_budget_summary(self, _info: graphene.ResolveInfo) -> BudgetSummaryType:
        user = get_current_user_required()
        service = BudgetService(UUID(str(user.id)))
        summary = service.get_summary()
        return BudgetSummaryType(
            total_budgeted=summary["total_budgeted"],
            total_spent=summary["total_spent"],
            total_remaining=summary["total_remaining"],
            percentage_used=summary["percentage_used"],
            budget_count=summary["budget_count"],
        )
