from __future__ import annotations

from .blueprint import budget_bp
from .resources import (
    BudgetCollectionResource,
    BudgetResource,
    BudgetSummaryResource,
)

_ROUTES_REGISTERED = False


def register_budget_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    budget_bp.add_url_rule(
        "",
        view_func=BudgetCollectionResource.as_view("budget_collection"),
        methods=["GET", "POST"],
    )
    budget_bp.add_url_rule(
        "/summary",
        view_func=BudgetSummaryResource.as_view("budget_summary"),
        methods=["GET"],
    )
    budget_bp.add_url_rule(
        "/<uuid:budget_id>",
        view_func=BudgetResource.as_view("budget_resource"),
        methods=["GET", "PATCH", "DELETE"],
    )

    _ROUTES_REGISTERED = True


register_budget_routes()
