"""Lightweight serializers for Alert and AlertPreference domain objects."""

from __future__ import annotations

from typing import TypedDict

from app.models.alert import Alert, AlertPreference


class AlertPayload(TypedDict):
    id: str
    user_id: str
    category: str
    status: str | None
    entity_type: str | None
    entity_id: str | None
    triggered_at: str | None
    sent_at: str | None
    created_at: str | None


class AlertPreferencePayload(TypedDict):
    id: str
    user_id: str
    category: str
    enabled: bool
    global_opt_out: bool
    updated_at: str | None


def serialize_alert(alert: Alert) -> AlertPayload:
    return {
        "id": str(alert.id),
        "user_id": str(alert.user_id),
        "category": alert.category,
        "status": alert.status.value if alert.status else None,
        "entity_type": alert.entity_type,
        "entity_id": str(alert.entity_id) if alert.entity_id else None,
        "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
        "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def serialize_preference(pref: AlertPreference) -> AlertPreferencePayload:
    return {
        "id": str(pref.id),
        "user_id": str(pref.user_id),
        "category": pref.category,
        "enabled": pref.enabled,
        "global_opt_out": pref.global_opt_out,
        "updated_at": pref.updated_at.isoformat() if pref.updated_at else None,
    }
