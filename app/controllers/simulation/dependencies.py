from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from flask import Flask, current_app

from app.application.services.simulation_application_service import (
    SimulationApplicationService,
)

SIMULATION_DEPENDENCIES_EXTENSION_KEY = "simulation_dependencies"


@dataclass(frozen=True)
class SimulationDependencies:
    simulation_application_service_factory: Callable[
        [UUID], SimulationApplicationService
    ]


def _default_dependencies() -> SimulationDependencies:
    return SimulationDependencies(
        simulation_application_service_factory=SimulationApplicationService.with_defaults,
    )


def register_simulation_dependencies(
    app: Flask,
    dependencies: SimulationDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(SIMULATION_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_simulation_dependencies() -> SimulationDependencies:
    configured = current_app.extensions.get(SIMULATION_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, SimulationDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[SIMULATION_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
