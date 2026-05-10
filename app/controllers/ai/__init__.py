from . import routes as _routes  # noqa: F401
from .blueprint import ai_bp
from .resources import (
    AIGoalProjectionResource,
    AISpendingInsightsResource,
    AIWeeklySummaryResource,
)

__all__ = [
    "ai_bp",
    "AISpendingInsightsResource",
    "AIGoalProjectionResource",
    "AIWeeklySummaryResource",
]
