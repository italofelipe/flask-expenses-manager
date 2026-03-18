"""Subscription service — J9 (billing / plan management).

Encapsulates all business logic for reading and mutating subscription state,
keeping controllers thin and provider-agnostic.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from app.extensions.database import db
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.billing_adapter import BillingProvider

_FREE_PLAN_CODE = "free"


def get_or_create_subscription(user_id: UUID) -> Subscription:
    """Return the active Subscription for *user_id*.

    Creates a free-tier record if none exists yet.
    """
    subscription = cast(
        Subscription | None,
        Subscription.query.filter_by(user_id=user_id).first(),
    )
    if subscription is None:
        subscription = Subscription(
            user_id=user_id,
            plan_code=_FREE_PLAN_CODE,
            status=SubscriptionStatus.FREE,
        )
        db.session.add(subscription)
        db.session.commit()
    return subscription


def sync_subscription_from_provider(
    subscription: Subscription,
    provider: BillingProvider,
) -> Subscription:
    """Pull the latest state from *provider* and persist it to *subscription*.

    Only performs an update when the subscription has a ``provider_subscription_id``
    set; otherwise the record is returned unchanged (free-tier users have no
    provider-side subscription to sync).
    """
    if not subscription.provider_subscription_id:
        return subscription

    data = provider.get_subscription(subscription.provider_subscription_id)

    raw_status = data.get("status", "")
    try:
        subscription.status = SubscriptionStatus(raw_status)
    except ValueError:
        # Unknown status from provider — leave existing status intact.
        pass

    if "plan_code" in data:
        subscription.plan_code = data["plan_code"]
    if "current_period_start" in data and data["current_period_start"] is not None:
        subscription.current_period_start = data["current_period_start"]
    if "current_period_end" in data and data["current_period_end"] is not None:
        subscription.current_period_end = data["current_period_end"]

    db.session.commit()
    return subscription


def cancel_subscription(
    subscription: Subscription,
    provider: BillingProvider,
) -> Subscription:
    """Cancel *subscription* in both the provider and the local database.

    If the subscription has no provider ID the status is set to CANCELED locally
    without making a provider call.
    """
    if subscription.provider_subscription_id:
        provider.cancel_subscription(subscription.provider_subscription_id)

    subscription.status = SubscriptionStatus.CANCELED
    db.session.commit()
    return subscription
