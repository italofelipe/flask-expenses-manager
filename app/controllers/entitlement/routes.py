from __future__ import annotations

from .blueprint import entitlement_bp
from .resources import (
    AdminEntitlementGrantResource,
    AdminEntitlementRevokeResource,
    EntitlementCheckResource,
    EntitlementCollectionResource,
)

_ROUTES_REGISTERED = False


def register_entitlement_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    entitlement_bp.add_url_rule(
        "",
        view_func=EntitlementCollectionResource.as_view("entitlement_collection"),
        methods=["GET"],
    )
    entitlement_bp.add_url_rule(
        "/check",
        view_func=EntitlementCheckResource.as_view("entitlement_check"),
        methods=["GET"],
    )
    entitlement_bp.add_url_rule(
        "/admin",
        view_func=AdminEntitlementGrantResource.as_view("admin_entitlement_grant"),
        methods=["POST"],
    )
    entitlement_bp.add_url_rule(
        "/admin/<uuid:entitlement_id>",
        view_func=AdminEntitlementRevokeResource.as_view("admin_entitlement_revoke"),
        methods=["DELETE"],
    )

    _ROUTES_REGISTERED = True


register_entitlement_routes()
