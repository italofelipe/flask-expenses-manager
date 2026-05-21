from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserProfile,
)
from app.graphql.types import UserType

# The GraphQL UserType exposes the legacy v2 fields **plus** the new email
# verification fields. The legacy REST v2 contract stays frozen and pops those
# 4 fields in ``to_user_profile_payload``; GraphQL needs them, so we build the
# payload directly from the dataclass here.
AuthenticatedUserGraphQLPayload = dict[str, Any]


def to_authenticated_user_graphql_payload(
    profile: AuthenticatedUserProfile,
) -> AuthenticatedUserGraphQLPayload:
    payload = asdict(profile)
    payload.pop("entitlements_version", None)
    return payload


def to_authenticated_user_type(profile: AuthenticatedUserProfile) -> UserType:
    return UserType(**to_authenticated_user_graphql_payload(profile))


__all__ = [
    "AuthenticatedUserGraphQLPayload",
    "to_authenticated_user_graphql_payload",
    "to_authenticated_user_type",
]
