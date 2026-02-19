"""User controller compatibility facade."""

from app.controllers.user import (
    UserDependencies,
    UserMeResource,
    UserProfileResource,
    _parse_positive_int,
    assign_user_profile_fields,
    filter_transactions,
    get_user_dependencies,
    register_user_dependencies,
    user_bp,
    validate_user_token,
)
from app.controllers.user.contracts import compat_error as _compat_error
from app.controllers.user.contracts import compat_success as _compat_success
from app.controllers.user.contracts import is_v2_contract as _is_v2_contract
from app.controllers.user.helpers import (
    _serialize_user_profile,
    _validation_error_response,
)

__all__ = [
    "user_bp",
    "UserDependencies",
    "register_user_dependencies",
    "get_user_dependencies",
    "UserProfileResource",
    "UserMeResource",
    "assign_user_profile_fields",
    "validate_user_token",
    "filter_transactions",
    "_parse_positive_int",
    "_is_v2_contract",
    "_compat_success",
    "_compat_error",
    "_serialize_user_profile",
    "_validation_error_response",
]
