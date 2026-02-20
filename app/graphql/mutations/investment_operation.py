from __future__ import annotations

from typing import Any
from uuid import UUID

import graphene

from app.application.services.investment_application_service import (
    InvestmentApplicationError,
    InvestmentApplicationService,
)
from app.graphql.auth import get_current_user_required
from app.graphql.investment_presenters import raise_investment_graphql_error
from app.graphql.types import InvestmentOperationType
from app.services.investment_operation_service import InvestmentOperationError

# Keep legacy import path stable for tests and compatibility facades.
_LEGACY_INVESTMENT_OPERATION_ERROR = InvestmentOperationError


class AddInvestmentOperationMutation(graphene.Mutation):
    class Arguments:
        investment_id = graphene.UUID(required=True)
        operation_type = graphene.String(required=True)
        quantity = graphene.String(required=True)
        unit_price = graphene.String(required=True)
        fees = graphene.String()
        executed_at = graphene.String()
        notes = graphene.String()

    item = graphene.Field(InvestmentOperationType, required=True)
    message = graphene.String(required=True)

    def mutate(
        self,
        info: graphene.ResolveInfo,
        investment_id: UUID,
        **kwargs: Any,
    ) -> "AddInvestmentOperationMutation":
        user = get_current_user_required()
        service = InvestmentApplicationService.with_defaults(user.id)
        try:
            operation_data = service.create_operation(investment_id, kwargs)
        except InvestmentApplicationError as exc:
            raise_investment_graphql_error(exc)
        return AddInvestmentOperationMutation(
            message="Operação registrada com sucesso",
            item=InvestmentOperationType(**operation_data),
        )


class UpdateInvestmentOperationMutation(graphene.Mutation):
    class Arguments:
        investment_id = graphene.UUID(required=True)
        operation_id = graphene.UUID(required=True)
        operation_type = graphene.String()
        quantity = graphene.String()
        unit_price = graphene.String()
        fees = graphene.String()
        executed_at = graphene.String()
        notes = graphene.String()

    item = graphene.Field(InvestmentOperationType, required=True)
    message = graphene.String(required=True)

    def mutate(
        self,
        info: graphene.ResolveInfo,
        investment_id: UUID,
        operation_id: UUID,
        **kwargs: Any,
    ) -> "UpdateInvestmentOperationMutation":
        user = get_current_user_required()
        service = InvestmentApplicationService.with_defaults(user.id)
        try:
            operation_data = service.update_operation(
                investment_id, operation_id, kwargs
            )
        except InvestmentApplicationError as exc:
            raise_investment_graphql_error(exc)
        return UpdateInvestmentOperationMutation(
            message="Operação atualizada com sucesso",
            item=InvestmentOperationType(**operation_data),
        )


class DeleteInvestmentOperationMutation(graphene.Mutation):
    class Arguments:
        investment_id = graphene.UUID(required=True)
        operation_id = graphene.UUID(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, investment_id: UUID, operation_id: UUID
    ) -> "DeleteInvestmentOperationMutation":
        user = get_current_user_required()
        service = InvestmentApplicationService.with_defaults(user.id)
        try:
            service.delete_operation(investment_id, operation_id)
        except InvestmentApplicationError as exc:
            raise_investment_graphql_error(exc)
        return DeleteInvestmentOperationMutation(
            ok=True, message="Operação removida com sucesso"
        )
