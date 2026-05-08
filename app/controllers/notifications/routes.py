from __future__ import annotations

from .blueprint import notifications_bp
from .resources import PushSubscribeResource, PushUnsubscribeResource

_ROUTES_REGISTERED = False


def register_notification_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    notifications_bp.add_url_rule(
        "/subscribe",
        view_func=PushSubscribeResource.as_view("push_subscribe"),
        methods=["POST"],
    )
    notifications_bp.add_url_rule(
        "/unsubscribe",
        view_func=PushUnsubscribeResource.as_view("push_unsubscribe"),
        methods=["POST"],
    )
    _ROUTES_REGISTERED = True


register_notification_routes()
