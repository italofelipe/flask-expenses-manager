"""Backward-compatible re-exports for transaction report resources.

All resource classes and legacy symbols re-exported to keep routes.py,
tests, and other callers working without modification.
"""

from __future__ import annotations

from app.controllers.transaction.analytics_resources import (
    TransactionDeletedResource,
    TransactionDuePeriodResource,
    TransactionExpensePeriodResource,
    TransactionMonthlyDashboardResource,
    TransactionSummaryResource,
)
from app.controllers.transaction.detail_resources import (
    TransactionDetailResource,
    TransactionForceDeleteResource,
    TransactionRestoreResource,
)
from app.controllers.transaction.list_resources import (
    TransactionCollectionResource,
    TransactionListActiveResource,
    _guard_revoked_token,
    _resolve_transaction_ordering,
)
from app.services.transaction_analytics_service import TransactionAnalyticsService

_LEGACY_ANALYTICS_SERVICE = TransactionAnalyticsService

__all__ = [
    "TransactionCollectionResource",
    "TransactionDetailResource",
    "TransactionSummaryResource",
    "TransactionMonthlyDashboardResource",
    "TransactionForceDeleteResource",
    "TransactionExpensePeriodResource",
    "TransactionDeletedResource",
    "TransactionDuePeriodResource",
    "TransactionRestoreResource",
    "TransactionListActiveResource",
    "_guard_revoked_token",
    "_resolve_transaction_ordering",
    "TransactionAnalyticsService",
]
