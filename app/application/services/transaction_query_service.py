from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Literal, TypedDict, cast
from uuid import UUID

from sqlalchemy import case, func

from app.application.services.transaction_application_service import (
    TransactionApplicationService,
)
from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.wallet import Wallet
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


class TransactionTrendsMonthEntry(TypedDict):
    month: str
    income: float
    expenses: float
    balance: float


class TransactionTrendsResult(TypedDict):
    months: int
    series: list[TransactionTrendsMonthEntry]


SurvivalClassification = Literal["critical", "attention", "comfortable", "secure"]


class SurvivalIndexResult(TypedDict):
    survival_months: float | None
    total_assets: float
    avg_monthly_expense: float
    classification: SurvivalClassification | None
    period_analyzed_months: int


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

    def get_dashboard_trends(self, *, months: int) -> TransactionTrendsResult:
        """Compute monthly income/expense/balance for the last N months.

        Only months that have at least one paid transaction are included.
        Results are ordered most-recent first.
        """
        today = date.today()
        # Build the first day of each of the last `months` calendar months.
        month_starts: list[date] = []
        for i in range(months):
            # Walk back month by month from current month
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_starts.append(date(year, month, 1))

        # Compute last-day of month helper
        def _last_day(d: date) -> date:
            next_month = d.replace(day=28) + timedelta(days=4)
            return next_month.replace(day=1) - timedelta(days=1)

        series: list[TransactionTrendsMonthEntry] = []
        for ms in month_starts:
            me = _last_day(ms)
            month_label = ms.strftime("%Y-%m")

            row = (
                db.session.query(
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    Transaction.type == TransactionType.INCOME,
                                    Transaction.amount,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("income"),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    Transaction.type == TransactionType.EXPENSE,
                                    Transaction.amount,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("expenses"),
                    func.count(Transaction.id).label("tx_count"),
                )
                .filter(
                    Transaction.user_id == self._user_id,
                    Transaction.deleted.is_(False),
                    Transaction.status == TransactionStatus.PAID,
                    Transaction.due_date >= ms,
                    Transaction.due_date <= me,
                )
                .one()
            )

            if int(row.tx_count or 0) == 0:
                continue

            income = float(row.income or 0)
            expenses = float(row.expenses or 0)
            series.append(
                {
                    "month": month_label,
                    "income": income,
                    "expenses": expenses,
                    "balance": round(income - expenses, 2),
                }
            )

        return {"months": months, "series": series}

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
        base_query = self._build_period_query(
            start_date=start_date,
            end_date=end_date,
        )
        total_transactions, income_transactions, expense_transactions = (
            self._build_period_counts(
                start_date=start_date,
                end_date=end_date,
            )
        )

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
            "expenses": [serialize_transaction_payload(item) for item in expenses],
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

    def _build_period_query(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> Any:
        query = Transaction.query.filter_by(user_id=self._user_id, deleted=False)
        if start_date is not None:
            query = query.filter(Transaction.due_date >= start_date)
        if end_date is not None:
            query = query.filter(Transaction.due_date <= end_date)
        return query

    def _build_period_counts(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[int, int, int]:
        counts_query = db.session.query(
            func.count(Transaction.id).label("total_transactions"),
            func.coalesce(
                func.sum(
                    case((Transaction.type == TransactionType.INCOME, 1), else_=0)
                ),
                0,
            ).label("income_transactions"),
            func.coalesce(
                func.sum(
                    case((Transaction.type == TransactionType.EXPENSE, 1), else_=0)
                ),
                0,
            ).label("expense_transactions"),
        ).filter(Transaction.user_id == self._user_id, Transaction.deleted.is_(False))
        if start_date is not None:
            counts_query = counts_query.filter(Transaction.due_date >= start_date)
        if end_date is not None:
            counts_query = counts_query.filter(Transaction.due_date <= end_date)
        row = counts_query.one()
        return (
            int(row.total_transactions or 0),
            int(row.income_transactions or 0),
            int(row.expense_transactions or 0),
        )

    def get_survival_index(self, *, period_months: int = 3) -> SurvivalIndexResult:
        """Compute burn-rate survival index.

        total_assets / avg_monthly_expense = months of runway.
        avg_monthly_expense is the mean of PAID expenses across the last
        *period_months* calendar months.
        """
        today = date.today()

        # --- Total assets: wallet entries marked as on-wallet, with a value ---
        assets_row = (
            db.session.query(func.coalesce(func.sum(Wallet.value), 0).label("total"))
            .filter(
                Wallet.user_id == self._user_id,
                Wallet.should_be_on_wallet.is_(True),
                Wallet.value.isnot(None),
            )
            .one()
        )
        total_assets = float(assets_row.total or 0)

        # --- Build period: 3 complete calendar months before current month ---
        # e.g. today=April → period Jan 1 – March 31
        year = today.year
        anchor_month = today.month - period_months
        while anchor_month <= 0:
            anchor_month += 12
            year -= 1
        period_start = date(year, anchor_month, 1)

        # Last day of previous complete month (avoid partial current month)
        first_of_current = today.replace(day=1)
        period_end = first_of_current - timedelta(days=1)

        # Total expenses in period (PAID, non-deleted)
        expense_row = (
            db.session.query(
                func.coalesce(func.sum(Transaction.amount), 0).label("total")
            )
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.deleted.is_(False),
                Transaction.type == TransactionType.EXPENSE,
                Transaction.status == TransactionStatus.PAID,
                Transaction.due_date >= period_start,
                Transaction.due_date <= period_end,
            )
            .one()
        )
        total_expense = float(expense_row.total or 0)
        avg_monthly_expense = round(total_expense / period_months, 2)

        # --- Edge cases ---
        if avg_monthly_expense == 0:
            return {
                "survival_months": None,
                "total_assets": round(total_assets, 2),
                "avg_monthly_expense": 0.0,
                "classification": None,
                "period_analyzed_months": period_months,
            }

        survival_months = round(total_assets / avg_monthly_expense, 2)
        classification = _classify_survival(survival_months)

        return {
            "survival_months": survival_months,
            "total_assets": round(total_assets, 2),
            "avg_monthly_expense": avg_monthly_expense,
            "classification": classification,
            "period_analyzed_months": period_months,
        }

    def _application_service(self) -> TransactionApplicationService:
        return self._dependencies.transaction_application_service_factory(self._user_id)


def _classify_survival(months: float) -> SurvivalClassification:
    if months < 3:
        return "critical"
    if months < 6:
        return "attention"
    if months <= 12:
        return "comfortable"
    return "secure"


__all__ = [
    "SurvivalClassification",
    "SurvivalIndexResult",
    "TransactionCountsPayload",
    "TransactionDashboardResult",
    "TransactionDueRangeResult",
    "TransactionExpensePeriodResult",
    "TransactionListResult",
    "TransactionPaginationPayload",
    "TransactionQueryDependencies",
    "TransactionQueryService",
    "TransactionSummaryResult",
    "TransactionTrendsMonthEntry",
    "TransactionTrendsResult",
]
