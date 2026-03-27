from . import routes as _routes  # noqa: F401
from .blueprint import dashboard_bp
from .resources import DashboardOverviewResource

__all__ = ["dashboard_bp", "DashboardOverviewResource"]
