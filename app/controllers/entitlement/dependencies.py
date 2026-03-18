from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from flask import Flask, current_app

from app.application.services.entitlement_application_service import (
    EntitlementApplicationService,
)

ENTITLEMENT_DEPENDENCIES_EXTENSION_KEY = "entitlement_dependencies"


@dataclass(frozen=True)
class EntitlementDependencies:
    entitlement_application_service_factory: Callable[
        [UUID], EntitlementApplicationService
    ]


def _default_dependencies() -> EntitlementDependencies:
    return EntitlementDependencies(
        entitlement_application_service_factory=EntitlementApplicationService.with_defaults,
    )


def register_entitlement_dependencies(
    app: Flask,
    dependencies: EntitlementDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(ENTITLEMENT_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_entitlement_dependencies() -> EntitlementDependencies:
    configured = current_app.extensions.get(ENTITLEMENT_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, EntitlementDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[ENTITLEMENT_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
