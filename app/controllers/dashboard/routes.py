from __future__ import annotations

from .blueprint import dashboard_bp
from .resources import (
    DashboardOverviewResource,
    DashboardSurvivalIndexResource,
    DashboardTrendsResource,
    DashboardWeeklySummaryResource,
)

_ROUTES_REGISTERED = False


def register_dashboard_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    dashboard_bp.add_url_rule(
        "/overview",
        view_func=DashboardOverviewResource.as_view("overview"),
        methods=["GET"],
    )
    dashboard_bp.add_url_rule(
        "/trends",
        view_func=DashboardTrendsResource.as_view("trends"),
        methods=["GET"],
    )
    dashboard_bp.add_url_rule(
        "/survival-index",
        view_func=DashboardSurvivalIndexResource.as_view("survival_index"),
        methods=["GET"],
    )
    dashboard_bp.add_url_rule(
        "/weekly-summary",
        view_func=DashboardWeeklySummaryResource.as_view("weekly_summary"),
        methods=["GET"],
    )
    _ROUTES_REGISTERED = True


register_dashboard_routes()
