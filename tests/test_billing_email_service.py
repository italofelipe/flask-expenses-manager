from __future__ import annotations

import uuid

from app.application.services.billing_email_service import dispatch_billing_email
from app.models.subscription import BillingCycle, Subscription, SubscriptionStatus
from app.models.user import User
from app.services.email_provider import get_email_outbox


def test_billing_email_service_sends_payment_confirmed_email(app) -> None:
    with app.app_context():
        user = User(
            id=uuid.uuid4(),
            name="Auraxis User",
            email="billing@email.com",
            password="hash",
        )
        subscription = Subscription(
            user_id=user.id,
            plan_code="premium",
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
        )

        dispatch_billing_email(
            user=user,
            subscription=subscription,
            event_type="PAYMENT_RECEIVED",
        )

        outbox = get_email_outbox()
        assert len(outbox) == 1
        assert outbox[0]["email"] == "billing@email.com"
        assert outbox[0]["tag"] == "billing_payment_confirmed"


def test_billing_email_service_sends_payment_failed_email(app) -> None:
    with app.app_context():
        user = User(
            id=uuid.uuid4(),
            name="Auraxis User",
            email="billing@email.com",
            password="hash",
        )
        subscription = Subscription(
            user_id=user.id,
            plan_code="premium",
            status=SubscriptionStatus.PAST_DUE,
            billing_cycle=BillingCycle.MONTHLY,
        )

        dispatch_billing_email(
            user=user,
            subscription=subscription,
            event_type="PAYMENT_OVERDUE",
        )

        outbox = get_email_outbox()
        assert len(outbox) == 1
        assert outbox[0]["tag"] == "billing_payment_failed"
