from __future__ import annotations

from uuid import UUID

import graphene
from graphql import GraphQLError

from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.controllers.transaction.utils import serialize_transaction
from app.graphql.auth import get_current_user_required
from app.graphql.schema_utils import (
    _apply_due_date_range_filter,
    _apply_status_filter,
    _apply_type_filter,
    _assert_owned_investment_access,
    _get_owned_wallet_or_error,
    _parse_month,
    _parse_optional_date,
    _user_to_graphql_payload,
    _validate_pagination_values,
    _wallet_to_graphql_payload,
)
from app.graphql.types import (
    DashboardCategoriesType,
    DashboardCategoryType,
    DashboardCountsType,
    DashboardStatusCountsType,
    DashboardTotalsType,
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
    TickerType,
    TransactionDashboardPayloadType,
    TransactionListPayloadType,
    TransactionSummaryPayloadType,
    TransactionTypeObject,
    UserType,
    WalletHistoryItemType,
    WalletHistoryPayloadType,
    WalletListPayloadType,
    WalletType,
)
from app.models.transaction import Transaction, TransactionType
from app.models.user_ticker import UserTicker
from app.models.wallet import Wallet
from app.services.investment_operation_service import (
    InvestmentOperationError,
    InvestmentOperationService,
)
from app.services.portfolio_history_service import PortfolioHistoryService
from app.services.portfolio_valuation_service import PortfolioValuationService
from app.services.transaction_analytics_service import TransactionAnalyticsService


def _paginate(total: int, page: int, per_page: int) -> PaginationType:
    pages = (total + per_page - 1) // per_page if total else 0
    return PaginationType(total=total, page=page, per_page=per_page, pages=pages)


def _serialize_transaction_items(
    transactions: list[Transaction],
) -> list[TransactionTypeObject]:
    return [
        TransactionTypeObject(**serialize_transaction(item)) for item in transactions
    ]


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    transactions = graphene.Field(
        TransactionListPayloadType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
        type=graphene.String(),
        status=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
    )
    transaction_summary = graphene.Field(
        TransactionSummaryPayloadType,
        month=graphene.String(required=True),
        page=graphene.Int(default_value=1),
        page_size=graphene.Int(default_value=10),
    )
    transaction_dashboard = graphene.Field(
        TransactionDashboardPayloadType, month=graphene.String(required=True)
    )
    wallet_entries = graphene.Field(
        WalletListPayloadType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
    )
    wallet_history = graphene.Field(
        WalletHistoryPayloadType,
        investment_id=graphene.UUID(required=True),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=5),
    )
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
    tickers = graphene.List(TickerType)

    def resolve_me(self, info: graphene.ResolveInfo) -> UserType:
        user = get_current_user_required()
        return UserType(**_user_to_graphql_payload(user))

    def resolve_transactions(
        self,
        info: graphene.ResolveInfo,
        page: int,
        per_page: int,
        type: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> TransactionListPayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        query = Transaction.query.filter_by(user_id=user.id, deleted=False)
        query = _apply_type_filter(query, type)
        query = _apply_status_filter(query, status)
        query = _apply_due_date_range_filter(query, start_date, end_date)

        total = query.count()
        items = (
            query.order_by(Transaction.due_date.desc(), Transaction.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return TransactionListPayloadType(
            items=_serialize_transaction_items(items),
            pagination=_paginate(total=total, page=page, per_page=per_page),
        )

    def resolve_transaction_summary(
        self,
        info: graphene.ResolveInfo,
        month: str,
        page: int,
        page_size: int,
    ) -> TransactionSummaryPayloadType:
        _validate_pagination_values(page, page_size)
        user = get_current_user_required()
        year, month_number = _parse_month(month)
        analytics = TransactionAnalyticsService(user.id)
        transactions = analytics.get_month_transactions(
            year=year, month_number=month_number
        )
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )

        total = len(transactions)
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = transactions[start:end]
        return TransactionSummaryPayloadType(
            month=month,
            income_total=float(aggregates["income_total"]),
            expense_total=float(aggregates["expense_total"]),
            items=_serialize_transaction_items(paged_items),
            pagination=_paginate(total=total, page=page, per_page=page_size),
        )

    def resolve_transaction_dashboard(
        self, info: graphene.ResolveInfo, month: str
    ) -> TransactionDashboardPayloadType:
        user = get_current_user_required()
        year, month_number = _parse_month(month)
        analytics = TransactionAnalyticsService(user.id)
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )
        status_counts = analytics.get_status_counts(
            year=year, month_number=month_number
        )
        top_expense = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.EXPENSE,
        )
        top_income = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.INCOME,
        )

        return TransactionDashboardPayloadType(
            month=month,
            totals=DashboardTotalsType(
                income_total=float(aggregates["income_total"]),
                expense_total=float(aggregates["expense_total"]),
                balance=float(aggregates["balance"]),
            ),
            counts=DashboardCountsType(
                total_transactions=aggregates["total_transactions"],
                income_transactions=aggregates["income_transactions"],
                expense_transactions=aggregates["expense_transactions"],
                status=DashboardStatusCountsType(
                    paid=status_counts["paid"],
                    pending=status_counts["pending"],
                    cancelled=status_counts["cancelled"],
                    postponed=status_counts["postponed"],
                    overdue=status_counts["overdue"],
                ),
            ),
            top_categories=DashboardCategoriesType(
                expense=[DashboardCategoryType(**item) for item in top_expense],
                income=[DashboardCategoryType(**item) for item in top_income],
            ),
        )

    def resolve_wallet_entries(
        self, info: graphene.ResolveInfo, page: int, per_page: int
    ) -> WalletListPayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        pagination = (
            Wallet.query.filter_by(user_id=user.id)
            .order_by(Wallet.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        items = [
            WalletType(**_wallet_to_graphql_payload(item)) for item in pagination.items
        ]
        return WalletListPayloadType(
            items=items,
            pagination=_paginate(
                total=pagination.total,
                page=pagination.page,
                per_page=pagination.per_page,
            ),
        )

    def resolve_wallet_history(
        self,
        info: graphene.ResolveInfo,
        investment_id: UUID,
        page: int,
        per_page: int,
    ) -> WalletHistoryPayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        investment = _get_owned_wallet_or_error(
            investment_id,
            user.id,
            forbidden_message=(
                "Você não tem permissão para ver o histórico deste investimento."
            ),
        )

        history = investment.history or []
        sorted_history = sorted(
            history,
            key=lambda item: (
                item.get("originalQuantity", 0) or 0,
                item.get("changeDate", ""),
            ),
            reverse=True,
        )
        total = len(sorted_history)
        start = (page - 1) * per_page
        end = start + per_page
        items = sorted_history[start:end]

        pages = (total + per_page - 1) // per_page if per_page and total else 0
        mapped_items = [
            WalletHistoryItemType(
                original_quantity=item.get("originalQuantity"),
                original_value=item.get("originalValue"),
                change_type=item.get("changeType"),
                change_date=item.get("changeDate"),
            )
            for item in items
        ]
        return WalletHistoryPayloadType(
            items=mapped_items,
            pagination=PaginationType(
                total=total,
                page=page,
                per_page=per_page,
                pages=pages,
            ),
        )

    def resolve_tickers(self, info: graphene.ResolveInfo) -> list[TickerType]:
        user = get_current_user_required()
        tickers = UserTicker.query.filter_by(user_id=user.id).all()
        return [
            TickerType(
                id=str(item.id),
                symbol=item.symbol,
                quantity=item.quantity,
                type=item.type,
            )
            for item in tickers
        ]

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
