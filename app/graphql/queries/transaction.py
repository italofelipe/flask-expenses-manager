from __future__ import annotations

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.queries.common import paginate, serialize_transaction_items
from app.graphql.schema_utils import (
    _apply_due_date_range_filter,
    _apply_status_filter,
    _apply_type_filter,
    _parse_month,
    _validate_pagination_values,
)
from app.graphql.types import (
    DashboardCategoriesType,
    DashboardCategoryType,
    DashboardCountsType,
    DashboardStatusCountsType,
    DashboardTotalsType,
    TransactionDashboardPayloadType,
    TransactionListPayloadType,
    TransactionSummaryPayloadType,
)
from app.models.transaction import Transaction, TransactionType
from app.services.transaction_analytics_service import TransactionAnalyticsService


class TransactionQueryMixin:
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
        TransactionDashboardPayloadType,
        month=graphene.String(required=True),
    )

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
            items=serialize_transaction_items(items),
            pagination=paginate(total=total, page=page, per_page=per_page),
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
            items=serialize_transaction_items(paged_items),
            pagination=paginate(total=total, page=page, per_page=page_size),
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
