"""Alert REST resources — J11-2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from flask import request
from flask_apispec.views import MethodResource

from app.auth import current_user_id
from app.controllers.response_contract import ResponseContractError
from app.services.alert_service import (
    AlertServiceError,
)
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import (
    alert_contract_error_response,
    alert_service_error_response,
    compat_success,
)
from .dependencies import get_alert_dependencies
from .serializers import serialize_alert, serialize_preference


@dataclass(frozen=True)
class AlertPreferenceInput:
    enabled: bool
    channels: list[str]
    global_opt_out: bool


def _require_bool(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ResponseContractError(
        f"Campo '{field_name}' inválido.",
        code="VALIDATION_ERROR",
        status_code=400,
        details={field_name: ["must_be_boolean"]},
        legacy_payload={"error": f"Campo '{field_name}' inválido."},
    )


def _parse_channels(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ResponseContractError(
            "Campo 'channels' inválido.",
            code="VALIDATION_ERROR",
            status_code=400,
            details={"channels": ["must_be_string_list"]},
            legacy_payload={"error": "Campo 'channels' inválido."},
        )
    return value


def _parse_alert_preference_input(payload: object) -> AlertPreferenceInput:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ResponseContractError(
            "Payload inválido.",
            code="VALIDATION_ERROR",
            status_code=400,
            details={"body": ["must_be_object"]},
            legacy_payload={"error": "Payload inválido."},
        )
    enabled = _require_bool(payload.get("enabled", True), "enabled")
    global_opt_out = _require_bool(
        payload.get("global_opt_out", False),
        "global_opt_out",
    )
    return AlertPreferenceInput(
        enabled=enabled,
        channels=_parse_channels(payload.get("channels")),
        global_opt_out=global_opt_out,
    )


class AlertCollectionResource(MethodResource):
    """GET /alerts — list alerts for the authenticated user."""

    @jwt_required()
    def get(self) -> Any:
        user_id: UUID = current_user_id()
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        dependencies = get_alert_dependencies()
        alerts = (
            dependencies.get_unread_alerts(user_id)
            if unread_only
            else dependencies.get_user_alerts(user_id)
        )
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
        dependencies = get_alert_dependencies()
        try:
            alert = dependencies.mark_read(alert_id, user_id)
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
        dependencies = get_alert_dependencies()
        try:
            dependencies.delete_alert(alert_id, user_id)
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
        prefs = get_alert_dependencies().get_preferences(user_id)
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
        try:
            parsed = _parse_alert_preference_input(request.get_json(silent=True))
            pref = get_alert_dependencies().upsert_preference(
                user_id,
                category,
                parsed.enabled,
                parsed.channels,
                parsed.global_opt_out,
            )
        except ResponseContractError as exc:
            return alert_contract_error_response(exc)
        except AlertServiceError as exc:
            return alert_service_error_response(exc)

        serialized = serialize_preference(pref)
        return compat_success(
            legacy_payload={"preference": serialized},
            status_code=200,
            message="Preferência de alerta atualizada com sucesso",
            data={"preference": serialized},
        )
