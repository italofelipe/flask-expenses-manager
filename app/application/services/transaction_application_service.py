"""Transaction Application Service — public façade.

This module is the backward-compatible entry point for all transaction
operations.  It composes:

- ``TransactionLedgerService`` — CRUD, validations, list queries
- Analytics delegation — month summary and dashboard (via
  ``TransactionAnalyticsService``)

All existing import paths continue to work unchanged:

    from app.application.services.transaction_application_service import (
        TransactionApplicationService,
        TransactionApplicationError,
    )
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.services.transaction_ledger_service import (
    TransactionApplicationError,
    TransactionLedgerService,
    _parse_month,
    _resolve_month_summary_page,
    _serialize_transaction,
)
from app.utils.pagination import PaginatedResponse

__all__ = [
    "TransactionApplicationService",
    "TransactionApplicationError",
]


class TransactionApplicationService(TransactionLedgerService):
    """Façade that extends the ledger with analytics and dashboard methods.

    Inherits all CRUD and list operations from ``TransactionLedgerService``.
    Adds aggregation/reporting methods that delegate to
    ``TransactionAnalyticsService``.
    """

    # ------------------------------------------------------------------
    # Analytics / reporting (delegates to TransactionAnalyticsService)
    # ------------------------------------------------------------------

    def get_month_summary(
        self,
        *,
        month: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        year, month_number, normalized_month = _parse_month(month)
        analytics = self._analytics_service_factory(self._user_id)
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )
        total_transactions, transactions = _resolve_month_summary_page(
            analytics=analytics,
            year=year,
            month_number=month_number,
            page=page,
            page_size=page_size,
        )
        serialized = [_serialize_transaction(item) for item in transactions]
        paginated = PaginatedResponse.format(
            serialized, total_transactions, page, page_size
        )
        return {
            "month": normalized_month,
            "income_total": float(aggregates["income_total"]),
            "expense_total": float(aggregates["expense_total"]),
            "paginated": paginated,
        }

    def get_month_dashboard(self, *, month: str) -> dict[str, Any]:
        """Build the dashboard overview payload.

        PERF: previously 4 SQL queries (get_month_aggregates +
        get_status_counts + get_top_categories x2). Now 2 queries:
          - Query 1: get_dashboard_overview_coalesced (totals + status)
          - Query 2: get_top_categories_both (income + expense UNION ALL)
        """
        year, month_number, normalized_month = _parse_month(month)
        analytics = self._analytics_service_factory(self._user_id)

        # Query 1: aggregates + status breakdown (replaces 2 queries)
        overview = analytics.get_dashboard_overview_coalesced(
            year=year, month_number=month_number
        )
        # Query 2: top categories both types in UNION ALL (replaces 2)
        categories = analytics.get_top_categories_both(
            year=year, month_number=month_number
        )

        return {
            "month": normalized_month,
            "income_total": float(overview["income_total"]),
            "expense_total": float(overview["expense_total"]),
            "balance": float(overview["balance"]),
            "counts": {
                "total_transactions": overview["total_transactions"],
                "income_transactions": overview["income_transactions"],
                "expense_transactions": overview["expense_transactions"],
                "status": overview["status"],
            },
            "top_expense_categories": categories["top_expense_categories"],
            "top_income_categories": categories["top_income_categories"],
        }

    # ------------------------------------------------------------------
    # Back-compat factory (re-exported from parent, typed as subclass)
    # ------------------------------------------------------------------

    @classmethod
    def with_defaults(cls, user_id: UUID) -> TransactionApplicationService:
        from app.services.transaction_analytics_service import (
            TransactionAnalyticsService,
        )

        return cls(
            user_id=user_id,
            analytics_service_factory=TransactionAnalyticsService,
        )
