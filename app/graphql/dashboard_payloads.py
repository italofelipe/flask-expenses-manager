from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from app.graphql.types import (
    DashboardCategoriesType,
    DashboardCategoryType,
    DashboardCountsType,
    DashboardStatusCountsType,
    DashboardTotalsType,
    TransactionDashboardPayloadType,
    WeeklyComparisonType,
    WeeklyPeriodTotalsType,
    WeeklySummaryPayloadType,
    WeeklySummarySeriesEntryType,
)


def _get_float_value(payload: Mapping[str, object], key: str) -> float:
    value = payload[key]
    if not isinstance(value, str | int | float):
        raise TypeError(f"Campo '{key}' do dashboard deve ser numérico.")
    return float(value)


def _get_int_value(payload: Mapping[str, object], key: str) -> int:
    value = payload[key]
    if not isinstance(value, str | int):
        raise TypeError(f"Campo '{key}' do dashboard deve ser inteiro.")
    return int(value)


def build_dashboard_overview_payload(
    result: Mapping[str, object],
) -> TransactionDashboardPayloadType:
    counts = cast(Mapping[str, object], result["counts"])
    status_counts = cast(Mapping[str, object], counts["status"])
    expense_categories = cast(list[dict[str, object]], result["top_expense_categories"])
    income_categories = cast(list[dict[str, object]], result["top_income_categories"])

    return TransactionDashboardPayloadType(
        month=str(result["month"]),
        totals=DashboardTotalsType(
            income_total=_get_float_value(result, "income_total"),
            expense_total=_get_float_value(result, "expense_total"),
            balance=_get_float_value(result, "balance"),
        ),
        counts=DashboardCountsType(
            total_transactions=_get_int_value(counts, "total_transactions"),
            income_transactions=_get_int_value(counts, "income_transactions"),
            expense_transactions=_get_int_value(counts, "expense_transactions"),
            status=DashboardStatusCountsType(
                paid=_get_int_value(status_counts, "paid"),
                pending=_get_int_value(status_counts, "pending"),
                cancelled=_get_int_value(status_counts, "cancelled"),
                postponed=_get_int_value(status_counts, "postponed"),
                overdue=_get_int_value(status_counts, "overdue"),
            ),
        ),
        top_categories=DashboardCategoriesType(
            expense=[
                DashboardCategoryType(**item)
                for item in expense_categories
                if isinstance(item, dict)
            ],
            income=[
                DashboardCategoryType(**item)
                for item in income_categories
                if isinstance(item, dict)
            ],
        ),
    )


def build_weekly_summary_payload(
    result: Mapping[str, object],
) -> WeeklySummaryPayloadType:
    def _period_totals(d: Mapping[str, object]) -> WeeklyPeriodTotalsType:
        return WeeklyPeriodTotalsType(
            start=str(d["start"]),
            end=str(d["end"]),
            income=float(d["income"]),  # type: ignore[arg-type]
            expense=float(d["expense"]),  # type: ignore[arg-type]
            balance=float(d["balance"]),  # type: ignore[arg-type]
            transaction_count=_get_int_value(d, "transaction_count"),
        )

    cmp = cast(Mapping[str, object], result["comparison"])
    raw_series = cast(list[dict[str, object]], result["series"])

    return WeeklySummaryPayloadType(
        current_week=_period_totals(cast(Mapping[str, object], result["current_week"])),
        previous_week=_period_totals(
            cast(Mapping[str, object], result["previous_week"])
        ),
        comparison=WeeklyComparisonType(
            income_delta=float(cmp["income_delta"]),  # type: ignore[arg-type]
            income_delta_percent=(
                float(cmp["income_delta_percent"])  # type: ignore[arg-type]
                if cmp["income_delta_percent"] is not None
                else None
            ),
            expense_delta=float(cmp["expense_delta"]),  # type: ignore[arg-type]
            expense_delta_percent=(
                float(cmp["expense_delta_percent"])  # type: ignore[arg-type]
                if cmp["expense_delta_percent"] is not None
                else None
            ),
            balance_delta=float(cmp["balance_delta"]),  # type: ignore[arg-type]
            balance_delta_percent=(
                float(cmp["balance_delta_percent"])  # type: ignore[arg-type]
                if cmp["balance_delta_percent"] is not None
                else None
            ),
        ),
        series=[
            WeeklySummarySeriesEntryType(
                date=str(e["date"]),
                income=float(e["income"]),  # type: ignore[arg-type]
                expense=float(e["expense"]),  # type: ignore[arg-type]
                balance=float(e["balance"]),  # type: ignore[arg-type]
            )
            for e in raw_series
        ],
        period=str(result["period"]),
        series_start=str(result["series_start"]),
        series_end=str(result["series_end"]),
    )


__all__ = ["build_dashboard_overview_payload", "build_weekly_summary_payload"]
