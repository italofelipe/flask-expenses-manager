from __future__ import annotations

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.schema_utils import _user_to_graphql_payload
from app.graphql.types import UserType


class UserQueryMixin:
    me = graphene.Field(UserType)

    def resolve_me(self, info: graphene.ResolveInfo) -> UserType:
        user = get_current_user_required()
        return UserType(**_user_to_graphql_payload(user))
