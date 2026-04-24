"""Plan feature matrix — J12 (subscription entitlement enforcement).

Maps each plan slug to the set of feature keys it grants.
"""

from __future__ import annotations

PLAN_FEATURES: dict[str, list[str]] = {
    "free": ["basic_simulations", "wallet_read"],
    "premium": [
        "basic_simulations",
        "wallet_read",
        "advanced_simulations",
        "export_pdf",
        "shared_entries",
        "focus_mode",
    ],
    "trial": [
        "basic_simulations",
        "wallet_read",
        "advanced_simulations",
        "export_pdf",
        "shared_entries",
        "focus_mode",
    ],
}

#: Features that are exclusive to paid plans (premium/trial).
#: Revoked when a subscription downgrades to free or is canceled.
PREMIUM_FEATURES: frozenset[str] = frozenset(PLAN_FEATURES["premium"]) - frozenset(
    PLAN_FEATURES["free"]
)
