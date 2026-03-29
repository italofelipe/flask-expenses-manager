"""Alert controller compatibility facade."""

from app.controllers.alert import (
    AlertCollectionResource,
    AlertPreferenceCollectionResource,
    AlertPreferenceResource,
    AlertReadResource,
    AlertResource,
    alert_bp,
    register_alert_dependencies,
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
