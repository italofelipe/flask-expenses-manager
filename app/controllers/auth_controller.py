"""Auth controller compatibility facade."""

from app.controllers.auth import (
    AuthResource,
    LogoutResource,
    RegisterResource,
    auth_bp,
    handle_webargs_error,
)
from app.controllers.auth.contracts import (
    AUTH_BACKEND_UNAVAILABLE_CODE,
    AUTH_BACKEND_UNAVAILABLE_MESSAGE,
)
from app.controllers.auth.contracts import (
    auth_backend_unavailable_response as _auth_backend_unavailable_response,
)
from app.controllers.auth.contracts import compat_error as _compat_error
from app.controllers.auth.contracts import compat_success as _compat_success
from app.controllers.auth.contracts import is_v2_contract as _is_v2_contract
from app.controllers.auth.contracts import (
    registration_ack_payload as _registration_ack_payload,
)
from app.controllers.auth.guard import guard_login_check as _guard_login_check
from app.controllers.auth.guard import guard_register_failure as _guard_register_failure
from app.controllers.auth.guard import guard_register_success as _guard_register_success

__all__ = [
    "auth_bp",
    "RegisterResource",
    "AuthResource",
    "LogoutResource",
    "handle_webargs_error",
    "_is_v2_contract",
    "_compat_success",
    "_compat_error",
    "_registration_ack_payload",
    "_auth_backend_unavailable_response",
    "_guard_login_check",
    "_guard_register_failure",
    "_guard_register_success",
    "AUTH_BACKEND_UNAVAILABLE_MESSAGE",
    "AUTH_BACKEND_UNAVAILABLE_CODE",
]
