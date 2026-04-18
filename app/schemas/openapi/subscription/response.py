"""Serialisation helpers for the subscription domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.subscription import Subscription

from app.config.billing_plans import canonical_offer_slug


def serialize_subscription(sub: Subscription) -> dict[str, Any]:
    offer_code = canonical_offer_slug(sub.plan_code, sub.billing_cycle)
    return {
        "id": str(sub.id),
        "user_id": str(sub.user_id),
        "plan_code": sub.plan_code,
        "offer_code": offer_code,
        "status": sub.status.value,
        "billing_cycle": sub.billing_cycle.value if sub.billing_cycle else None,
        "provider": sub.provider,
        "provider_subscription_id": sub.provider_subscription_id,
        "trial_ends_at": (sub.trial_ends_at.isoformat() if sub.trial_ends_at else None),
        "current_period_start": (
            sub.current_period_start.isoformat() if sub.current_period_start else None
        ),
        "current_period_end": (
            sub.current_period_end.isoformat() if sub.current_period_end else None
        ),
        "canceled_at": (sub.canceled_at.isoformat() if sub.canceled_at else None),
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }
