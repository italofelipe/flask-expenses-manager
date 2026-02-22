from __future__ import annotations

from .blueprint import user_bp
from .me_resource import UserMeResource
from .profile_resource import UserProfileResource

_ROUTES_REGISTERED = False


def register_user_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    user_bp.add_url_rule(
        "/profile",
        view_func=UserProfileResource.as_view("profile"),
        methods=["GET", "PUT"],
    )
    user_bp.add_url_rule("/me", view_func=UserMeResource.as_view("me"))
    _ROUTES_REGISTERED = True


register_user_routes()
