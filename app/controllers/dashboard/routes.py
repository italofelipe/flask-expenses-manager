from __future__ import annotations

from .blueprint import dashboard_bp
from .resources import DashboardOverviewResource

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
    _ROUTES_REGISTERED = True


register_dashboard_routes()
