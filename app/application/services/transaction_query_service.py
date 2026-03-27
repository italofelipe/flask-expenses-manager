from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, TypedDict, cast
from uuid import UUID

from app.application.services.transaction_application_service import (
    TransactionApplicationService,
)
from app.models.transaction import Transaction, TransactionType
from app.services.transaction_analytics_service import TransactionAnalyticsService
from app.services.transaction_serialization import (
    TransactionPayload,
    serialize_transaction_payload,
)


class TransactionPaginationPayload(TypedDict):
    total: int
    page: int
    per_page: int
    pages: int


class TransactionCountsPayload(TypedDict):
    total_transactions: int
    income_transactions: int
    expense_transactions: int


class TransactionListResult(TypedDict):
    items: list[TransactionPayload]
    pagination: TransactionPaginationPayload


class TransactionSummaryPaginationPayload(TypedDict):
    total: int
    page: int
    page_size: int
    has_next_page: bool
    data: list[TransactionPayload]


class TransactionSummaryResult(TypedDict):
    month: str
    income_total: float
    expense_total: float
    paginated: TransactionSummaryPaginationPayload


class TransactionDashboardCountsPayload(TypedDict):
    total_transactions: int
    income_transactions: int
    expense_transactions: int
    status: dict[str, int]


class TransactionDashboardCategoryPayload(TypedDict):
    tag_id: str | None
    category_name: str
    total_amount: float
    transactions_count: int


class TransactionDashboardResult(TypedDict):
    month: str
    income_total: float
    expense_total: float
    balance: float
    counts: TransactionDashboardCountsPayload
    top_expense_categories: list[TransactionDashboardCategoryPayload]
    top_income_categories: list[TransactionDashboardCategoryPayload]


class TransactionDueRangeResult(TypedDict):
    items: list[TransactionPayload]
    counts: TransactionCountsPayload
    pagination: TransactionPaginationPayload


class TransactionExpensePeriodResult(TypedDict):
    expenses: list[TransactionPayload]
    counts: TransactionCountsPayload
    pagination: TransactionPaginationPayload


@dataclass(frozen=True)
class TransactionQueryDependencies:
    transaction_application_service_factory: Callable[
        [UUID], TransactionApplicationService
    ]
    analytics_service_factory: Callable[[UUID], TransactionAnalyticsService]


class TransactionQueryService:
    def __init__(
        self,
        *,
        user_id: UUID,
        dependencies: TransactionQueryDependencies,
    ) -> None:
        self._user_id = user_id
        self._dependencies = dependencies

    @classmethod
    def with_defaults(cls, user_id: UUID) -> TransactionQueryService:
        return cls(
            user_id=user_id,
            dependencies=TransactionQueryDependencies(
                transaction_application_service_factory=(
                    TransactionApplicationService.with_defaults
                ),
                analytics_service_factory=TransactionAnalyticsService,
            ),
        )

    def get_transaction(self, transaction_id: UUID) -> TransactionPayload:
        return self._application_service().get_transaction(transaction_id)

    def get_active_transactions(
        self,
        *,
        page: int,
        per_page: int,
        transaction_type: str | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
        tag_id: UUID | None,
        account_id: UUID | None,
        credit_card_id: UUID | None,
    ) -> TransactionListResult:
        return cast(
            TransactionListResult,
            self._application_service().get_active_transactions(
                page=page,
                per_page=per_page,
                transaction_type=transaction_type,
                status=status,
                start_date=start_date,
                end_date=end_date,
                tag_id=tag_id,
                account_id=account_id,
                credit_card_id=credit_card_id,
            ),
        )

    def get_month_summary(
        self,
        *,
        month: str,
        page: int,
        per_page: int,
    ) -> TransactionSummaryResult:
        return cast(
            TransactionSummaryResult,
            self._application_service().get_month_summary(
                month=month,
                page=page,
                page_size=per_page,
            ),
        )

    def get_dashboard_overview(self, *, month: str) -> TransactionDashboardResult:
        return cast(
            TransactionDashboardResult,
            self._application_service().get_month_dashboard(month=month),
        )

    def get_due_transactions(
        self,
        *,
        start_date: str | date | None,
        end_date: str | date | None,
        page: int,
        per_page: int,
        order_by: str,
    ) -> TransactionDueRangeResult:
        return cast(
            TransactionDueRangeResult,
            self._application_service().get_due_transactions(
                start_date=start_date,
                end_date=end_date,
                page=page,
                per_page=per_page,
                order_by=order_by,
            ),
        )

    def get_expense_period(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        page: int,
        per_page: int,
        ordering_clause: Any,
    ) -> TransactionExpensePeriodResult:
        base_query = Transaction.query.filter_by(user_id=self._user_id, deleted=False)
        if start_date is not None:
            base_query = base_query.filter(Transaction.due_date >= start_date)
        if end_date is not None:
            base_query = base_query.filter(Transaction.due_date <= end_date)

        total_transactions = base_query.count()
        income_transactions = base_query.filter(
            Transaction.type == TransactionType.INCOME
        ).count()
        expense_transactions = base_query.filter(
            Transaction.type == TransactionType.EXPENSE
        ).count()

        expenses_query = base_query.filter(Transaction.type == TransactionType.EXPENSE)
        total_expenses = expense_transactions
        pages = (total_expenses + per_page - 1) // per_page if total_expenses else 0
        expenses = (
            expenses_query.order_by(ordering_clause)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return {
            "expenses": [
                self._application_service().get_transaction(item.id)
                for item in expenses
            ],
            "counts": {
                "total_transactions": total_transactions,
                "income_transactions": income_transactions,
                "expense_transactions": expense_transactions,
            },
            "pagination": {
                "total": total_expenses,
                "page": page,
                "per_page": per_page,
                "pages": pages,
            },
        }

    def list_deleted_transactions(self) -> list[TransactionPayload]:
        deleted_transactions = Transaction.query.filter_by(
            user_id=self._user_id,
            deleted=True,
        ).all()
        return [serialize_transaction_payload(item) for item in deleted_transactions]

    def _application_service(self) -> TransactionApplicationService:
        return self._dependencies.transaction_application_service_factory(self._user_id)


__all__ = [
    "TransactionCountsPayload",
    "TransactionDashboardResult",
    "TransactionDueRangeResult",
    "TransactionExpensePeriodResult",
    "TransactionListResult",
    "TransactionPaginationPayload",
    "TransactionQueryDependencies",
    "TransactionQueryService",
    "TransactionSummaryResult",
]
