"""GraphQL mutations for notification preferences (#836)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_VALIDATION,
    build_public_graphql_error,
)
from app.graphql.types import AlertPreferenceType
from app.services.alert_service import AlertServiceError, upsert_preference

_VALID_CATEGORIES = frozenset(
    {"due_soon", "wallet", "goals", "transactions", "subscription"}
)


class PreferenceInput(graphene.InputObjectType):
    category = graphene.String(required=True)
    enabled = graphene.Boolean(required=True)
    global_opt_out = graphene.Boolean()


class UpdateNotificationPreferencesMutation(graphene.Mutation):
    class Arguments:
        preferences = graphene.List(graphene.NonNull(PreferenceInput), required=True)

    message = graphene.String(required=True)
    preferences = graphene.List(graphene.NonNull(AlertPreferenceType), required=True)

    def mutate(
        self,
        info: graphene.ResolveInfo,
        preferences: list[Any],
    ) -> "UpdateNotificationPreferencesMutation":
        user = get_current_user_required()
        user_id = UUID(str(user.id))

        updated = []
        for pref_input in preferences:
            category = str(pref_input.category).strip().lower()
            if category not in _VALID_CATEGORIES:
                raise build_public_graphql_error(
                    f"Categoria inválida: {category!r}",
                    code=GRAPHQL_ERROR_CODE_VALIDATION,
                )
            try:
                pref = upsert_preference(
                    user_id,
                    category,
                    enabled=bool(pref_input.enabled),
                    global_opt_out=bool(pref_input.global_opt_out or False),
                )
                updated.append(
                    AlertPreferenceType(
                        category=pref.category,
                        enabled=pref.enabled,
                        global_opt_out=pref.global_opt_out,
                    )
                )
            except AlertServiceError as exc:
                raise build_public_graphql_error(
                    exc.message, code=GRAPHQL_ERROR_CODE_VALIDATION
                ) from exc

        return UpdateNotificationPreferencesMutation(
            message="Preferências de notificação atualizadas com sucesso",
            preferences=updated,
        )
