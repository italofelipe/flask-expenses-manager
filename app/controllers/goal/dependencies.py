from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from flask import Flask, current_app

from app.application.services.goal_application_service import GoalApplicationService

GOAL_DEPENDENCIES_EXTENSION_KEY = "goal_dependencies"


@dataclass(frozen=True)
class GoalDependencies:
    goal_application_service_factory: Callable[[UUID], GoalApplicationService]


def _default_dependencies() -> GoalDependencies:
    return GoalDependencies(
        goal_application_service_factory=GoalApplicationService.with_defaults,
    )


def register_goal_dependencies(
    app: Flask,
    dependencies: GoalDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(GOAL_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_goal_dependencies() -> GoalDependencies:
    configured = current_app.extensions.get(GOAL_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, GoalDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[GOAL_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
