from __future__ import annotations

import graphene

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserContextService,
)
from app.graphql.auth import get_current_user_required
from app.graphql.authenticated_user_presenters import to_authenticated_user_type
from app.graphql.types import UserType


class UserQueryMixin:
    me = graphene.Field(UserType)

    def resolve_me(self, _info: graphene.ResolveInfo) -> UserType:
        user = get_current_user_required()
        profile = AuthenticatedUserContextService.with_defaults().build_profile(user)
        return to_authenticated_user_type(profile)
