from __future__ import annotations

from .blueprint import simulation_bp
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

    _ROUTES_REGISTERED = True


register_simulation_routes()
