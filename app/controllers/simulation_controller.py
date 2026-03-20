"""Simulation controller compatibility facade."""

from app.controllers.simulation import (
    InstallmentVsCashCalculationResource,
    InstallmentVsCashSaveResource,
    SimulationCollectionResource,
    SimulationDependencies,
    SimulationGoalBridgeResource,
    SimulationPlannedExpenseBridgeResource,
    SimulationResource,
    get_simulation_dependencies,
    register_simulation_dependencies,
    simulation_bp,
)

__all__ = [
    "simulation_bp",
    "SimulationDependencies",
    "register_simulation_dependencies",
    "get_simulation_dependencies",
    "SimulationCollectionResource",
    "SimulationResource",
    "InstallmentVsCashCalculationResource",
    "InstallmentVsCashSaveResource",
    "SimulationGoalBridgeResource",
    "SimulationPlannedExpenseBridgeResource",
]
