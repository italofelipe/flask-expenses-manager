"""Payload types for the transaction query surface.

Shared TypedDict / Literal definitions consumed by
``TransactionQueryService`` and downstream controllers / resolvers. Lives
here (rather than inside the service module) so the service file stays
lean and other domains can import types without pulling the service's
dependency graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, TypedDict
from uuid import UUID

from app.application.services.transaction_application_service import (
    TransactionApplicationService,
)
from app.services.transaction_analytics_service import TransactionAnalyticsService
from app.services.transaction_serialization import TransactionPayload


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


class WeeklyPeriodTotals(TypedDict):
    start: str
    end: str
    income: float
    expense: float
    balance: float
    transaction_count: int


class WeeklyComparison(TypedDict):
    income_delta: float
    income_delta_percent: float | None
    expense_delta: float
    expense_delta_percent: float | None
    balance_delta: float
    balance_delta_percent: float | None


class WeeklySummarySeriesEntry(TypedDict):
    date: str
    income: float
    expense: float
    balance: float


class WeeklySummaryResult(TypedDict):
    current_week: WeeklyPeriodTotals
    previous_week: WeeklyPeriodTotals
    comparison: WeeklyComparison
    series: list[WeeklySummarySeriesEntry]
    period: str
    series_start: str
    series_end: str


@dataclass(frozen=True)
class TransactionQueryDependencies:
    transaction_application_service_factory: Callable[
        [UUID], TransactionApplicationService
    ]
    analytics_service_factory: Callable[[UUID], TransactionAnalyticsService]


__all__ = [
    "SurvivalClassification",
    "SurvivalIndexResult",
    "TransactionCountsPayload",
    "TransactionDashboardCategoryPayload",
    "TransactionDashboardCountsPayload",
    "TransactionDashboardResult",
    "TransactionDueRangeResult",
    "TransactionExpensePeriodResult",
    "TransactionListResult",
    "TransactionPaginationPayload",
    "TransactionQueryDependencies",
    "TransactionSummaryPaginationPayload",
    "TransactionSummaryResult",
    "TransactionTrendsMonthEntry",
    "TransactionTrendsResult",
    "WeeklyComparison",
    "WeeklyPeriodTotals",
    "WeeklySummaryResult",
    "WeeklySummarySeriesEntry",
]
