from __future__ import annotations

import graphene

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
    TransactionApplicationService,
)
from app.graphql.auth import get_current_user_required
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.graphql.queries.common import paginate, serialize_transaction_items
from app.graphql.schema_utils import (
    _apply_due_date_range_filter,
    _apply_status_filter,
    _apply_type_filter,
    _validate_pagination_values,
)
from app.graphql.types import (
    DashboardCategoriesType,
    DashboardCategoryType,
    DashboardCountsType,
    DashboardStatusCountsType,
    DashboardTotalsType,
    TransactionDashboardPayloadType,
    TransactionDueCountsType,
    TransactionDueRangePayloadType,
    TransactionListPayloadType,
    TransactionSummaryPayloadType,
    TransactionTypeObject,
)
from app.models.transaction import Transaction


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
    transaction_due_range = graphene.Field(
        TransactionDueRangePayloadType,
        initial_date=graphene.String(),
        final_date=graphene.String(),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
        order_by=graphene.String(default_value="overdue_first"),
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
        service = TransactionApplicationService.with_defaults(user.id)
        try:
            result = service.get_month_summary(
                month=month,
                page=page,
                page_size=page_size,
            )
        except TransactionApplicationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc

        paginated = result["paginated"]
        return TransactionSummaryPayloadType(
            month=str(result["month"]),
            income_total=float(result["income_total"]),
            expense_total=float(result["expense_total"]),
            items=[
                TransactionTypeObject(**item)
                for item in paginated["data"]
                if isinstance(item, dict)
            ],
            pagination=paginate(
                total=int(paginated["total"]),
                page=int(paginated["page"]),
                per_page=int(paginated["page_size"]),
            ),
        )

    def resolve_transaction_dashboard(
        self, info: graphene.ResolveInfo, month: str
    ) -> TransactionDashboardPayloadType:
        user = get_current_user_required()
        service = TransactionApplicationService.with_defaults(user.id)
        try:
            result = service.get_month_dashboard(month=month)
        except TransactionApplicationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc

        return TransactionDashboardPayloadType(
            month=str(result["month"]),
            totals=DashboardTotalsType(
                income_total=float(result["income_total"]),
                expense_total=float(result["expense_total"]),
                balance=float(result["balance"]),
            ),
            counts=DashboardCountsType(
                total_transactions=int(result["counts"]["total_transactions"]),
                income_transactions=int(result["counts"]["income_transactions"]),
                expense_transactions=int(result["counts"]["expense_transactions"]),
                status=DashboardStatusCountsType(
                    paid=int(result["counts"]["status"]["paid"]),
                    pending=int(result["counts"]["status"]["pending"]),
                    cancelled=int(result["counts"]["status"]["cancelled"]),
                    postponed=int(result["counts"]["status"]["postponed"]),
                    overdue=int(result["counts"]["status"]["overdue"]),
                ),
            ),
            top_categories=DashboardCategoriesType(
                expense=[
                    DashboardCategoryType(**item)
                    for item in result["top_expense_categories"]
                    if isinstance(item, dict)
                ],
                income=[
                    DashboardCategoryType(**item)
                    for item in result["top_income_categories"]
                    if isinstance(item, dict)
                ],
            ),
        )

    def resolve_transaction_due_range(
        self,
        info: graphene.ResolveInfo,
        initial_date: str | None = None,
        final_date: str | None = None,
        page: int = 1,
        per_page: int = 10,
        order_by: str = "overdue_first",
    ) -> TransactionDueRangePayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        service = TransactionApplicationService.with_defaults(user.id)
        try:
            result = service.get_due_transactions(
                initial_date=initial_date,
                final_date=final_date,
                page=page,
                per_page=per_page,
                order_by=order_by,
            )
        except TransactionApplicationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc

        counts = result["counts"]
        pagination = result["pagination"]
        return TransactionDueRangePayloadType(
            items=[
                TransactionTypeObject(**item)
                for item in result["items"]
                if isinstance(item, dict)
            ],
            counts=TransactionDueCountsType(
                total_transactions=int(counts["total_transactions"]),
                income_transactions=int(counts["income_transactions"]),
                expense_transactions=int(counts["expense_transactions"]),
            ),
            pagination=paginate(
                total=int(pagination["total"]),
                page=int(pagination["page"]),
                per_page=int(pagination["per_page"]),
            ),
        )
