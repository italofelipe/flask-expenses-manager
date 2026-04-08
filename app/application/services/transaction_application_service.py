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
from app.models.transaction import TransactionType
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
        year, month_number, normalized_month = _parse_month(month)
        analytics = self._analytics_service_factory(self._user_id)
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )
        status_counts = analytics.get_status_counts(
            year=year, month_number=month_number
        )
        top_expense_categories = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.EXPENSE,
        )
        top_income_categories = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.INCOME,
        )
        return {
            "month": normalized_month,
            "income_total": float(aggregates["income_total"]),
            "expense_total": float(aggregates["expense_total"]),
            "balance": float(aggregates["balance"]),
            "counts": {
                "total_transactions": aggregates["total_transactions"],
                "income_transactions": aggregates["income_transactions"],
                "expense_transactions": aggregates["expense_transactions"],
                "status": status_counts,
            },
            "top_expense_categories": top_expense_categories,
            "top_income_categories": top_income_categories,
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
