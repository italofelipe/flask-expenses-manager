from __future__ import annotations

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserProfile,
)
from app.graphql.types import UserType
from app.services.authenticated_user_payloads import (
    UserProfilePayload,
    to_user_profile_payload,
)

AuthenticatedUserGraphQLPayload = UserProfilePayload


def to_authenticated_user_graphql_payload(
    profile: AuthenticatedUserProfile,
) -> AuthenticatedUserGraphQLPayload:
    return to_user_profile_payload(profile)


def to_authenticated_user_type(profile: AuthenticatedUserProfile) -> UserType:
    return UserType(**to_authenticated_user_graphql_payload(profile))


__all__ = [
    "AuthenticatedUserGraphQLPayload",
    "to_authenticated_user_graphql_payload",
    "to_authenticated_user_type",
]
