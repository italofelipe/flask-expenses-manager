"""Alert controller compatibility facade."""

from app.controllers.alert import (
    AlertCollectionResource,
    AlertPreferenceCollectionResource,
    AlertPreferenceResource,
    AlertReadResource,
    AlertResource,
    alert_bp,
)

__all__ = [
    "alert_bp",
    "AlertCollectionResource",
    "AlertReadResource",
    "AlertResource",
    "AlertPreferenceCollectionResource",
    "AlertPreferenceResource",
]
