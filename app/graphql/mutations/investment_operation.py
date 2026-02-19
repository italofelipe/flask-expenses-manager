from __future__ import annotations

from typing import Any
from uuid import UUID

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.graphql.schema_utils import _assert_owned_investment_access
from app.graphql.types import InvestmentOperationType
from app.services.investment_operation_service import (
    InvestmentOperationError,
    InvestmentOperationService,
)


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
        _assert_owned_investment_access(investment_id, user.id)
        service = InvestmentOperationService(user.id)
        try:
            operation = service.create_operation(investment_id, kwargs)
        except InvestmentOperationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc
        return AddInvestmentOperationMutation(
            message="Operação registrada com sucesso",
            item=InvestmentOperationType(
                **InvestmentOperationService.serialize(operation)
            ),
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
        _assert_owned_investment_access(investment_id, user.id)
        service = InvestmentOperationService(user.id)
        try:
            operation = service.update_operation(investment_id, operation_id, kwargs)
        except InvestmentOperationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc
        return UpdateInvestmentOperationMutation(
            message="Operação atualizada com sucesso",
            item=InvestmentOperationType(
                **InvestmentOperationService.serialize(operation)
            ),
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
        _assert_owned_investment_access(investment_id, user.id)
        service = InvestmentOperationService(user.id)
        try:
            service.delete_operation(investment_id, operation_id)
        except InvestmentOperationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc
        return DeleteInvestmentOperationMutation(
            ok=True, message="Operação removida com sucesso"
        )
