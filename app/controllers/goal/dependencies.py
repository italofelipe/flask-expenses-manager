from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from flask import Flask, current_app

from app.services.goal_service import GoalService

GOAL_DEPENDENCIES_EXTENSION_KEY = "goal_dependencies"


@dataclass(frozen=True)
class GoalDependencies:
    goal_service_factory: Callable[[UUID], GoalService]


def _default_dependencies() -> GoalDependencies:
    return GoalDependencies(
        goal_service_factory=GoalService,
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
