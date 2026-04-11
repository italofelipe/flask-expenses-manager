"""REST resource for user notification preferences (#836)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, request
from flask_apispec.views import MethodResource

from app.auth import get_active_auth_context
from app.services.alert_service import (
    AlertServiceError,
    get_preferences,
    upsert_preference,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_error, compat_success

_VALID_CATEGORIES = frozenset(
    {"due_soon", "wallet", "goals", "transactions", "subscription"}
)


def _serialize_preference(pref: Any) -> dict[str, Any]:
    return {
        "category": pref.category,
        "enabled": pref.enabled,
        "global_opt_out": pref.global_opt_out,
    }


class NotificationPreferencesResource(MethodResource):
    @doc(
        description="Lista as preferências de notificação do usuário autenticado.",
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Preferências retornadas com sucesso"},
            401: {"description": "Token inválido ou expirado"},
        },
    )
    @jwt_required()
    def get(self) -> Response:
        auth = get_active_auth_context()
        prefs = get_preferences(UUID(auth.subject))
        serialized = [_serialize_preference(p) for p in prefs]
        return compat_success(
            legacy_payload={"preferences": serialized},
            status_code=200,
            message="Preferências de notificação retornadas com sucesso",
            data={"preferences": serialized},
        )

    @doc(
        description=(
            "Atualiza as preferências de notificação do usuário autenticado. "
            "Aceita uma lista de preferências para upsert."
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Preferências atualizadas com sucesso"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido ou expirado"},
        },
    )
    @jwt_required()
    def patch(self) -> Response:
        auth = get_active_auth_context()
        user_id = UUID(auth.subject)

        body: dict[str, Any] = request.get_json(silent=True) or {}
        preferences_raw = body.get("preferences")
        if not isinstance(preferences_raw, list):
            return compat_error(
                legacy_payload={
                    "error": "Campo 'preferences' é obrigatório e deve ser uma lista."
                },
                status_code=400,
                message="Campo 'preferences' é obrigatório e deve ser uma lista.",
                error_code="VALIDATION_ERROR",
            )

        updated = []
        for item in preferences_raw:
            if not isinstance(item, dict):
                return compat_error(
                    legacy_payload={"error": "Cada preferência deve ser um objeto."},
                    status_code=400,
                    message="Cada preferência deve ser um objeto.",
                    error_code="VALIDATION_ERROR",
                )
            category = str(item.get("category", "")).strip().lower()
            if not category or category not in _VALID_CATEGORIES:
                return compat_error(
                    legacy_payload={"error": f"Categoria inválida: {category!r}"},
                    status_code=400,
                    message=f"Categoria inválida: {category!r}",
                    error_code="VALIDATION_ERROR",
                )
            enabled = item.get("enabled")
            if not isinstance(enabled, bool):
                return compat_error(
                    legacy_payload={"error": "Campo 'enabled' deve ser booleano."},
                    status_code=400,
                    message="Campo 'enabled' deve ser booleano.",
                    error_code="VALIDATION_ERROR",
                )
            global_opt_out = bool(item.get("global_opt_out", False))
            try:
                pref = upsert_preference(
                    user_id,
                    category,
                    enabled=enabled,
                    global_opt_out=global_opt_out,
                )
                updated.append(_serialize_preference(pref))
            except AlertServiceError as exc:
                return compat_error(
                    legacy_payload={"error": exc.message},
                    status_code=exc.status_code,
                    message=exc.message,
                    error_code=exc.code,
                )

        return compat_success(
            legacy_payload={"preferences": updated},
            status_code=200,
            message="Preferências de notificação atualizadas com sucesso",
            data={"preferences": updated},
        )
