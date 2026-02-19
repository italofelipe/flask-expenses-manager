from __future__ import annotations

from uuid import UUID

import graphene
from graphql import GraphQLError

from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.graphql.auth import get_current_user_required
from app.graphql.schema_utils import (
    _assert_owned_investment_access,
    _parse_optional_date,
    _validate_pagination_values,
)
from app.graphql.types import (
    InvestmentInvestedAmountType,
    InvestmentOperationListPayloadType,
    InvestmentOperationSummaryType,
    InvestmentOperationType,
    InvestmentPositionType,
    PaginationType,
    PortfolioHistoryItemType,
    PortfolioHistoryPayloadType,
    PortfolioHistorySummaryType,
    PortfolioValuationItemType,
    PortfolioValuationPayloadType,
    PortfolioValuationSummaryType,
)
from app.services.investment_operation_service import (
    InvestmentOperationError,
    InvestmentOperationService,
)
from app.services.portfolio_history_service import PortfolioHistoryService
from app.services.portfolio_valuation_service import PortfolioValuationService


class InvestmentQueryMixin:
    investment_operations = graphene.Field(
        InvestmentOperationListPayloadType,
        investment_id=graphene.UUID(required=True),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
    )
    investment_operation_summary = graphene.Field(
        InvestmentOperationSummaryType,
        investment_id=graphene.UUID(required=True),
    )
    investment_position = graphene.Field(
        InvestmentPositionType,
        investment_id=graphene.UUID(required=True),
    )
    investment_invested_amount = graphene.Field(
        InvestmentInvestedAmountType,
        investment_id=graphene.UUID(required=True),
        date=graphene.String(required=True),
    )
    investment_valuation = graphene.Field(
        PortfolioValuationItemType,
        investment_id=graphene.UUID(required=True),
    )
    portfolio_valuation = graphene.Field(PortfolioValuationPayloadType)
    portfolio_valuation_history = graphene.Field(
        PortfolioHistoryPayloadType,
        start_date=graphene.String(),
        final_date=graphene.String(),
    )

    def resolve_investment_operations(
        self,
        info: graphene.ResolveInfo,
        investment_id: UUID,
        page: int,
        per_page: int,
    ) -> InvestmentOperationListPayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        _assert_owned_investment_access(investment_id, user.id)
        service = InvestmentOperationService(user.id)
        try:
            operations, pagination = service.list_operations(
                investment_id=investment_id, page=page, per_page=per_page
            )
        except InvestmentOperationError as exc:
            raise GraphQLError(exc.message) from exc

        items = [
            InvestmentOperationType(**InvestmentOperationService.serialize(item))
            for item in operations
        ]
        return InvestmentOperationListPayloadType(
            items=items,
            pagination=PaginationType(
                total=pagination["total"],
                page=pagination["page"],
                per_page=pagination["per_page"],
                pages=pagination["pages"],
            ),
        )

    def resolve_investment_operation_summary(
        self, info: graphene.ResolveInfo, investment_id: UUID
    ) -> InvestmentOperationSummaryType:
        user = get_current_user_required()
        _assert_owned_investment_access(investment_id, user.id)
        service = InvestmentOperationService(user.id)
        try:
            summary = service.get_summary(investment_id)
        except InvestmentOperationError as exc:
            raise GraphQLError(exc.message) from exc
        return InvestmentOperationSummaryType(**summary)

    def resolve_investment_position(
        self, info: graphene.ResolveInfo, investment_id: UUID
    ) -> InvestmentPositionType:
        user = get_current_user_required()
        _assert_owned_investment_access(investment_id, user.id)
        service = InvestmentOperationService(user.id)
        try:
            position = service.get_position(investment_id)
        except InvestmentOperationError as exc:
            raise GraphQLError(exc.message) from exc
        return InvestmentPositionType(**position)

    def resolve_investment_invested_amount(
        self, info: graphene.ResolveInfo, investment_id: UUID, date: str
    ) -> InvestmentInvestedAmountType:
        user = get_current_user_required()
        _assert_owned_investment_access(investment_id, user.id)
        operation_date = _parse_optional_date(date, "date")
        if operation_date is None:
            raise GraphQLError("Parâmetro 'date' é obrigatório.")

        service = InvestmentOperationService(user.id)
        try:
            result = service.get_invested_amount_by_date(investment_id, operation_date)
        except InvestmentOperationError as exc:
            raise GraphQLError(exc.message) from exc
        return InvestmentInvestedAmountType(**result)

    def resolve_investment_valuation(
        self, info: graphene.ResolveInfo, investment_id: UUID
    ) -> PortfolioValuationItemType:
        user = get_current_user_required()
        _assert_owned_investment_access(investment_id, user.id)
        service = PortfolioValuationService(user.id)
        try:
            payload = service.get_investment_current_valuation(investment_id)
        except InvestmentOperationError as exc:
            raise GraphQLError(exc.message) from exc
        return PortfolioValuationItemType(**payload)

    def resolve_portfolio_valuation(
        self, info: graphene.ResolveInfo
    ) -> PortfolioValuationPayloadType:
        user = get_current_user_required()
        service = PortfolioValuationService(user.id)
        payload = service.get_portfolio_current_valuation()
        return PortfolioValuationPayloadType(
            summary=PortfolioValuationSummaryType(**payload["summary"]),
            items=[PortfolioValuationItemType(**item) for item in payload["items"]],
        )

    def resolve_portfolio_valuation_history(
        self,
        info: graphene.ResolveInfo,
        start_date: str | None = None,
        final_date: str | None = None,
    ) -> PortfolioHistoryPayloadType:
        user = get_current_user_required()
        parsed_start_date = _parse_optional_date(start_date, "start_date")
        parsed_final_date = _parse_optional_date(final_date, "final_date")
        service = PortfolioHistoryService(user.id)
        try:
            payload = service.get_history(
                start_date=parsed_start_date, end_date=parsed_final_date
            )
        except ValueError as exc:
            mapped_error = map_validation_exception(
                exc,
                fallback_message="Parâmetros de período inválidos.",
            )
            raise GraphQLError(mapped_error.message) from exc
        return PortfolioHistoryPayloadType(
            summary=PortfolioHistorySummaryType(**payload["summary"]),
            items=[PortfolioHistoryItemType(**item) for item in payload["items"]],
        )
