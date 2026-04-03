from __future__ import annotations

from .blueprint import auth_bp
from .confirm_email_resource import ConfirmEmailResource
from .forgot_password_resource import ForgotPasswordResource
from .login_resource import AuthResource
from .logout_resource import LogoutResource
from .refresh_token_resource import RefreshTokenResource
from .register_resource import RegisterResource
from .resend_confirmation_resource import ResendConfirmationResource
from .reset_password_resource import ResetPasswordResource

_ROUTES_REGISTERED = False


def register_auth_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    auth_bp.add_url_rule(
        "/register", view_func=RegisterResource.as_view("registerresource")
    )
    auth_bp.add_url_rule("/login", view_func=AuthResource.as_view("authresource"))
    auth_bp.add_url_rule(
        "/refresh", view_func=RefreshTokenResource.as_view("refreshtokenresource")
    )
    auth_bp.add_url_rule("/logout", view_func=LogoutResource.as_view("logoutresource"))
    auth_bp.add_url_rule(
        "/password/forgot",
        view_func=ForgotPasswordResource.as_view("forgotpasswordresource"),
    )
    auth_bp.add_url_rule(
        "/password/reset",
        view_func=ResetPasswordResource.as_view("resetpasswordresource"),
    )
    auth_bp.add_url_rule(
        "/email/confirm",
        view_func=ConfirmEmailResource.as_view("confirmemailresource"),
    )
    auth_bp.add_url_rule(
        "/email/resend",
        view_func=ResendConfirmationResource.as_view("resendconfirmationresource"),
    )
    _ROUTES_REGISTERED = True


register_auth_routes()
