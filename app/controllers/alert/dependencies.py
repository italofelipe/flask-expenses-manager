from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from flask import Flask, current_app

from app.models.alert import Alert, AlertPreference
from app.services.alert_service import (
    delete_alert,
    get_preferences,
    get_user_alerts,
    mark_read,
    upsert_preference,
)

ALERT_DEPENDENCIES_EXTENSION_KEY = "alert_dependencies"


@dataclass(frozen=True)
class AlertDependencies:
    get_user_alerts: Callable[[UUID], list[Alert]]
    get_unread_alerts: Callable[[UUID], list[Alert]]
    mark_read: Callable[[UUID, UUID], Alert]
    delete_alert: Callable[[UUID, UUID], None]
    get_preferences: Callable[[UUID], list[AlertPreference]]
    upsert_preference: Callable[[UUID, str, bool, list[str], bool], AlertPreference]


def _default_dependencies() -> AlertDependencies:
    return AlertDependencies(
        get_user_alerts=lambda user_id: get_user_alerts(user_id, unread_only=False),
        get_unread_alerts=lambda user_id: get_user_alerts(user_id, unread_only=True),
        mark_read=mark_read,
        delete_alert=delete_alert,
        get_preferences=get_preferences,
        upsert_preference=lambda user_id, category, enabled, channels, global_opt_out: (
            upsert_preference(
                user_id=user_id,
                category=category,
                enabled=enabled,
                channels=channels,
                global_opt_out=global_opt_out,
            )
        ),
    )


def register_alert_dependencies(
    app: Flask,
    dependencies: AlertDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(ALERT_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_alert_dependencies() -> AlertDependencies:
    configured = current_app.extensions.get(ALERT_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, AlertDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[ALERT_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
