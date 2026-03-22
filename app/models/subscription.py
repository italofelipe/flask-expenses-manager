# mypy: disable-error-code="name-defined"
"""Subscription model — J9 (billing / plan management)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [str(item.value) for item in enum_cls]


class SubscriptionStatus(enum.Enum):
    FREE = "free"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class BillingCycle(enum.Enum):
    MONTHLY = "monthly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class Subscription(db.Model):
    """Canonical subscription state for a user.  One active record per user."""

    __tablename__ = "subscriptions"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_code = db.Column(db.String(40), nullable=False)
    status = db.Column(
        db.Enum(SubscriptionStatus, values_callable=_enum_values),
        nullable=False,
        default=SubscriptionStatus.FREE,
    )
    billing_cycle = db.Column(
        db.Enum(BillingCycle, values_callable=_enum_values), nullable=True
    )

    # Billing provider fields (Asaas)
    provider = db.Column(db.String(40), nullable=True)
    provider_subscription_id = db.Column(db.String(120), nullable=True, index=True)
    provider_customer_id = db.Column(db.String(120), nullable=True)
    # Idempotency key of the last processed webhook event
    provider_event_id = db.Column(db.String(120), nullable=True, index=True)

    # Period / lifecycle timestamps
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    grace_period_ends_at = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription user={self.user_id} plan={self.plan_code}"
            f" status={self.status}>"
        )
