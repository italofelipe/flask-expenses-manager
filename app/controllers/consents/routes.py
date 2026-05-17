"""URL rules for the LGPD versioned consents blueprint."""

from __future__ import annotations

from .blueprint import consents_bp
from .resources import ConsentCollectionResource, ConsentRevokeResource

_ROUTES_REGISTERED = False


def register_consent_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    consents_bp.add_url_rule(
        "",
        view_func=ConsentCollectionResource.as_view("consent_collection"),
        methods=["GET", "POST"],
    )
    consents_bp.add_url_rule(
        "/<string:kind>",
        view_func=ConsentRevokeResource.as_view("consent_revoke"),
        methods=["DELETE"],
    )
    _ROUTES_REGISTERED = True


register_consent_routes()
