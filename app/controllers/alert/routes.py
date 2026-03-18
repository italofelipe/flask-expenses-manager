from __future__ import annotations

from .blueprint import alert_bp
from .resources import (
    AlertCollectionResource,
    AlertPreferenceCollectionResource,
    AlertPreferenceResource,
    AlertReadResource,
    AlertResource,
)

_ROUTES_REGISTERED = False


def register_alert_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    # NOTE: static routes must be registered before parameterised ones to avoid
    # Flask matching /alerts/preferences as /alerts/<alert_id>.
    alert_bp.add_url_rule(
        "/preferences",
        view_func=AlertPreferenceCollectionResource.as_view(
            "alert_preference_collection"
        ),
        methods=["GET"],
    )
    alert_bp.add_url_rule(
        "/preferences/<string:category>",
        view_func=AlertPreferenceResource.as_view("alert_preference"),
        methods=["PUT"],
    )
    alert_bp.add_url_rule(
        "",
        view_func=AlertCollectionResource.as_view("alert_collection"),
        methods=["GET"],
    )
    alert_bp.add_url_rule(
        "/<uuid:alert_id>/read",
        view_func=AlertReadResource.as_view("alert_read"),
        methods=["POST"],
    )
    alert_bp.add_url_rule(
        "/<uuid:alert_id>",
        view_func=AlertResource.as_view("alert_resource"),
        methods=["DELETE"],
    )

    _ROUTES_REGISTERED = True


register_alert_routes()
