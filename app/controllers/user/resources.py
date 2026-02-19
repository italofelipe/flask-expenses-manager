"""
User resources compatibility facade.

This module keeps legacy import paths stable while implementation
is split into domain-focused modules.
"""

from .me_resource import UserMeResource
from .profile_resource import UserProfileResource
from .routes import register_user_routes as _register_user_routes  # noqa: F401

__all__ = ["UserProfileResource", "UserMeResource"]
