"""GraphQL queries for notification preferences (#836)."""

from __future__ import annotations

from uuid import UUID

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.types import AlertPreferenceType, NotificationPreferencesType
from app.services.alert_service import get_preferences


class NotificationQueryMixin:
    notification_preferences = graphene.Field(NotificationPreferencesType)

    def resolve_notification_preferences(
        self, _info: graphene.ResolveInfo
    ) -> NotificationPreferencesType:
        user = get_current_user_required()
        prefs = get_preferences(UUID(str(user.id)))
        items = [
            AlertPreferenceType(
                category=p.category,
                enabled=p.enabled,
                global_opt_out=p.global_opt_out,
            )
            for p in prefs
        ]
        return NotificationPreferencesType(preferences=items)
