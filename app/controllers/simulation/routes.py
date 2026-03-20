from __future__ import annotations

from .blueprint import simulation_bp
from .installment_vs_cash_resources import (
    InstallmentVsCashCalculationResource,
    InstallmentVsCashSaveResource,
    SimulationGoalBridgeResource,
    SimulationPlannedExpenseBridgeResource,
)
from .resources import SimulationCollectionResource, SimulationResource

_ROUTES_REGISTERED = False


def register_simulation_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    simulation_bp.add_url_rule(
        "",
        view_func=SimulationCollectionResource.as_view("simulation_collection"),
        methods=["GET", "POST"],
    )
    simulation_bp.add_url_rule(
        "/<uuid:simulation_id>",
        view_func=SimulationResource.as_view("simulation_resource"),
        methods=["GET", "DELETE"],
    )
    simulation_bp.add_url_rule(
        "/installment-vs-cash/calculate",
        view_func=InstallmentVsCashCalculationResource.as_view(
            "installment_vs_cash_calculation"
        ),
        methods=["POST"],
    )
    simulation_bp.add_url_rule(
        "/installment-vs-cash/save",
        view_func=InstallmentVsCashSaveResource.as_view("installment_vs_cash_save"),
        methods=["POST"],
    )
    simulation_bp.add_url_rule(
        "/<uuid:simulation_id>/goal",
        view_func=SimulationGoalBridgeResource.as_view("simulation_goal_bridge"),
        methods=["POST"],
    )
    simulation_bp.add_url_rule(
        "/<uuid:simulation_id>/planned-expense",
        view_func=SimulationPlannedExpenseBridgeResource.as_view(
            "simulation_planned_expense_bridge"
        ),
        methods=["POST"],
    )

    _ROUTES_REGISTERED = True


register_simulation_routes()
