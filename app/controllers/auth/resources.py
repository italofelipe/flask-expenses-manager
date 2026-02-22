"""
Auth resources compatibility facade.

This module keeps legacy import paths stable while the implementation
is split into domain-focused modules.
"""

from .error_handlers import handle_webargs_error
from .forgot_password_resource import ForgotPasswordResource
from .login_resource import AuthResource
from .logout_resource import LogoutResource
from .register_resource import RegisterResource
from .reset_password_resource import ResetPasswordResource
from .routes import register_auth_routes as _register_auth_routes  # noqa: F401

__all__ = [
    "RegisterResource",
    "AuthResource",
    "LogoutResource",
    "ForgotPasswordResource",
    "ResetPasswordResource",
    "handle_webargs_error",
]
