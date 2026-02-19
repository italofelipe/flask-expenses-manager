from __future__ import annotations

from .blueprint import auth_bp
from .login_resource import AuthResource
from .logout_resource import LogoutResource
from .register_resource import RegisterResource

_ROUTES_REGISTERED = False


def register_auth_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    auth_bp.add_url_rule(
        "/register", view_func=RegisterResource.as_view("registerresource")
    )
    auth_bp.add_url_rule("/login", view_func=AuthResource.as_view("authresource"))
    auth_bp.add_url_rule("/logout", view_func=LogoutResource.as_view("logoutresource"))
    _ROUTES_REGISTERED = True


register_auth_routes()
