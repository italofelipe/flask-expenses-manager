"""Goal controller compatibility facade."""

from app.controllers.goal import (
    GoalCollectionResource,
    GoalDependencies,
    GoalPlanResource,
    GoalResource,
    GoalSimulationResource,
    get_goal_dependencies,
    goal_bp,
    register_goal_dependencies,
)

__all__ = [
    "goal_bp",
    "GoalDependencies",
    "register_goal_dependencies",
    "get_goal_dependencies",
    "GoalCollectionResource",
    "GoalResource",
    "GoalPlanResource",
    "GoalSimulationResource",
]
