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


__all__ = ["build_dashboard_overview_payload"]
