from . import resources as _resources  # noqa: F401
from . import routes as _routes  # noqa: F401
from .blueprint import alert_bp
from .dependencies import register_alert_dependencies
from .resources import (
    AlertCollectionResource,
    AlertPreferenceCollectionResource,
    AlertPreferenceResource,
    AlertReadResource,
    AlertResource,
)

__all__ = [
    "alert_bp",
    "AlertCollectionResource",
    "AlertReadResource",
    "AlertResource",
    "AlertPreferenceCollectionResource",
    "AlertPreferenceResource",
    "register_alert_dependencies",
]
