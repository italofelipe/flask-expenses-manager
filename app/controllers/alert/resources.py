"""Alert REST resources — J11-2."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request
from flask_apispec.views import MethodResource

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_response
from app.services.alert_service import (
    AlertServiceError,
    delete_alert,
    get_preferences,
    get_user_alerts,
    mark_read,
    upsert_preference,
)
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import alert_service_error_response, compat_success
from .serializers import serialize_alert, serialize_preference


class AlertCollectionResource(MethodResource):
    """GET /alerts — list alerts for the authenticated user."""

    @jwt_required()
    def get(self) -> Any:
        user_id: UUID = current_user_id()
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        alerts = get_user_alerts(user_id, unread_only=unread_only)
        serialized = [serialize_alert(a) for a in alerts]
        return compat_success(
            legacy_payload={"alerts": serialized},
            status_code=200,
            message="Alertas listados com sucesso",
            data={"alerts": serialized},
        )


class AlertReadResource(MethodResource):
    """POST /alerts/<id>/read — mark alert as read."""

    @jwt_required()
    def post(self, alert_id: UUID) -> Any:
        user_id: UUID = current_user_id()
        try:
            alert = mark_read(alert_id, user_id)
        except AlertServiceError as exc:
            return alert_service_error_response(exc)
        serialized = serialize_alert(alert)
        return compat_success(
            legacy_payload={"alert": serialized},
            status_code=200,
            message="Alerta marcado como lido",
            data={"alert": serialized},
        )


class AlertResource(MethodResource):
    """DELETE /alerts/<id> — delete an alert."""

    @jwt_required()
    def delete(self, alert_id: UUID) -> Any:
        user_id: UUID = current_user_id()
        try:
            delete_alert(alert_id, user_id)
        except AlertServiceError as exc:
            return alert_service_error_response(exc)
        return compat_success(
            legacy_payload={"message": "Alerta removido com sucesso"},
            status_code=200,
            message="Alerta removido com sucesso",
            data={},
        )


class AlertPreferenceCollectionResource(MethodResource):
    """GET /alerts/preferences — list user alert preferences."""

    @jwt_required()
    def get(self) -> Any:
        user_id: UUID = current_user_id()
        prefs = get_preferences(user_id)
        serialized = [serialize_preference(p) for p in prefs]
        return compat_success(
            legacy_payload={"preferences": serialized},
            status_code=200,
            message="Preferências de alerta listadas com sucesso",
            data={"preferences": serialized},
        )


class AlertPreferenceResource(MethodResource):
    """PUT /alerts/preferences/<category> — create or update a preference."""

    @jwt_required()
    def put(self, category: str) -> Any:
        user_id: UUID = current_user_id()
        payload = request.get_json() or {}
        enabled = payload.get("enabled", True)
        channels = payload.get("channels", [])
        global_opt_out = payload.get("global_opt_out", False)

        try:
            pref = upsert_preference(
                user_id,
                category,
                enabled=bool(enabled),
                channels=channels,
                global_opt_out=bool(global_opt_out),
            )
        except Exception as exc:  # noqa: BLE001
            return compat_error_response(
                legacy_payload={"error": str(exc)},
                status_code=500,
                message=str(exc),
                error_code="INTERNAL_ERROR",
            )

        serialized = serialize_preference(pref)
        return compat_success(
            legacy_payload={"preference": serialized},
            status_code=200,
            message="Preferência de alerta atualizada com sucesso",
            data={"preference": serialized},
        )
