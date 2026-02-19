from __future__ import annotations

from .blueprint import transaction_bp
from .report_resources import (
    TransactionDeletedResource,
    TransactionExpensePeriodResource,
    TransactionForceDeleteResource,
    TransactionListActiveResource,
    TransactionMonthlyDashboardResource,
    TransactionRestoreResource,
    TransactionSummaryResource,
)
from .resources import TransactionResource

_ROUTES_REGISTERED = False


def register_transaction_routes() -> None:
    """Bind transaction REST endpoints once, preserving legacy endpoint names."""

    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    transaction_bp.add_url_rule(
        "", view_func=TransactionResource.as_view("transactionresource")
    )
    transaction_bp.add_url_rule(
        "/<uuid:transaction_id>",
        view_func=TransactionResource.as_view("transactionupdate"),
        methods=["PUT"],
    )
    transaction_bp.add_url_rule(
        "/<uuid:transaction_id>",
        view_func=TransactionResource.as_view("transactiondelete"),
        methods=["DELETE"],
    )
    transaction_bp.add_url_rule(
        "/restore/<uuid:transaction_id>",
        view_func=TransactionRestoreResource.as_view("transaction_restore"),
        methods=["PATCH"],
    )
    transaction_bp.add_url_rule(
        "/deleted",
        view_func=TransactionDeletedResource.as_view("transaction_list_deleted"),
        methods=["GET"],
    )
    transaction_bp.add_url_rule(
        "/<uuid:transaction_id>/force",
        view_func=TransactionForceDeleteResource.as_view("transaction_delete_force"),
        methods=["DELETE"],
    )
    transaction_bp.add_url_rule(
        "/summary",
        view_func=TransactionSummaryResource.as_view("transaction_monthly_summary"),
        methods=["GET"],
    )
    transaction_bp.add_url_rule(
        "/dashboard",
        view_func=TransactionMonthlyDashboardResource.as_view(
            "transaction_monthly_dashboard"
        ),
        methods=["GET"],
    )
    transaction_bp.add_url_rule(
        "/list",
        view_func=TransactionListActiveResource.as_view("transaction_list_active"),
        methods=["GET"],
    )
    transaction_bp.add_url_rule(
        "/expenses",
        view_func=TransactionExpensePeriodResource.as_view(
            "transaction_expense_period"
        ),
        methods=["GET"],
    )

    _ROUTES_REGISTERED = True


register_transaction_routes()
