from __future__ import annotations

from .blueprint import advisory_bp
from .resources import AdvisoryInsightsResource

_ROUTES_REGISTERED = False


def register_advisory_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    advisory_bp.add_url_rule(
        "/insights",
        view_func=AdvisoryInsightsResource.as_view("insights"),
        methods=["GET"],
    )
    _ROUTES_REGISTERED = True


register_advisory_routes()
