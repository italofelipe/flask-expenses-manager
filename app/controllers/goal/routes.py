from __future__ import annotations

from .blueprint import goal_bp
from .resources import (
    GoalCollectionResource,
    GoalPlanResource,
    GoalResource,
    GoalSimulationResource,
)

_ROUTES_REGISTERED = False


def register_goal_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    goal_bp.add_url_rule(
        "",
        view_func=GoalCollectionResource.as_view("goal_collection"),
        methods=["GET", "POST"],
    )
    goal_bp.add_url_rule(
        "/simulate",
        view_func=GoalSimulationResource.as_view("goal_simulation"),
        methods=["POST"],
    )
    goal_bp.add_url_rule(
        "/<uuid:goal_id>",
        view_func=GoalResource.as_view("goal_resource"),
        methods=["GET", "PUT", "DELETE"],
    )
    goal_bp.add_url_rule(
        "/<uuid:goal_id>/plan",
        view_func=GoalPlanResource.as_view("goal_plan"),
        methods=["GET"],
    )

    _ROUTES_REGISTERED = True


register_goal_routes()
