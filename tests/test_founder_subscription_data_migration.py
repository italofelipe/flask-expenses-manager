"""Regression tests for founder subscription data migration (#1250)."""

from __future__ import annotations

import importlib
import uuid
from datetime import datetime
from typing import Any

from app.extensions.database import db
from app.models.entitlement import Entitlement, EntitlementSource
from app.models.subscription import BillingCycle, Subscription, SubscriptionStatus
from app.models.user import User

_PREMIUM_FEATURES = {
    "basic_simulations",
    "wallet_read",
    "advanced_simulations",
    "export_pdf",
    "shared_entries",
    "focus_mode",
    "email_reminders",
}
_FOUNDER_USER_ID = uuid.UUID("ee8d33ca-0ac0-41cc-95bd-c4be49cbcbd5")
_FOUNDER_SUBSCRIPTION_ID = uuid.UUID("5428138f-be6b-48a5-bb8c-7a4f48522b01")


def _run_founder_subscription_migration(monkeypatch: Any) -> None:
    migration = importlib.import_module(
        "migrations.versions.ai6_founder_subscription_premium"
    )

    class _Context:
        connection = db.session.connection()

    class _Op:
        def get_context(self) -> _Context:
            return _Context()

    monkeypatch.setattr(migration, "op", _Op())
    migration.upgrade()
    db.session.commit()


def test_migration_promotes_existing_founder_subscription(app, monkeypatch) -> None:
    with app.app_context():
        founder = User(
            id=_FOUNDER_USER_ID,
            name="Felipe Italo",
            email="founder@auraxis.test",
            password="hash",
        )
        db.session.add(founder)
        db.session.flush()
        subscription = Subscription(
            user_id=founder.id,
            plan_code="free",
            status=SubscriptionStatus.FREE,
            billing_cycle=None,
            trial_ends_at=datetime(2026, 6, 1),
            canceled_at=datetime(2026, 5, 1),
        )
        db.session.add(subscription)
        db.session.commit()

        _run_founder_subscription_migration(monkeypatch)

        db.session.refresh(subscription)
        assert subscription.plan_code == "premium"
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.billing_cycle == BillingCycle.MONTHLY
        assert subscription.trial_ends_at is None
        assert subscription.canceled_at is None

        entitlements = Entitlement.query.filter_by(user_id=founder.id).all()
        granted_keys = {ent.feature_key for ent in entitlements}
        assert _PREMIUM_FEATURES.issubset(granted_keys)
        assert all(
            ent.source == EntitlementSource.SUBSCRIPTION
            for ent in entitlements
            if ent.feature_key in _PREMIUM_FEATURES
        )


def test_migration_inserts_subscription_when_founder_has_none(app, monkeypatch) -> None:
    with app.app_context():
        founder = User(
            id=_FOUNDER_USER_ID,
            name="Felipe Italo",
            email="founder@auraxis.test",
            password="hash",
        )
        db.session.add(founder)
        db.session.commit()

        _run_founder_subscription_migration(monkeypatch)

        subscription = Subscription.query.filter_by(user_id=founder.id).one()
        assert subscription.plan_code == "premium"
        assert subscription.id == _FOUNDER_SUBSCRIPTION_ID
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.billing_cycle == BillingCycle.MONTHLY

        granted_keys = {
            ent.feature_key for ent in Entitlement.query.filter_by(user_id=founder.id)
        }
        assert _PREMIUM_FEATURES.issubset(granted_keys)


def test_migration_does_not_promote_regular_free_users(app, monkeypatch) -> None:
    with app.app_context():
        user = User(
            name="Regular Free",
            email="regular-free@auraxis.test",
            password="hash",
        )
        db.session.add(user)
        db.session.flush()
        subscription = Subscription(
            user_id=user.id,
            plan_code="free",
            status=SubscriptionStatus.FREE,
        )
        db.session.add(subscription)
        db.session.commit()

        _run_founder_subscription_migration(monkeypatch)

        db.session.refresh(subscription)
        assert subscription.plan_code == "free"
        assert subscription.status == SubscriptionStatus.FREE
        assert subscription.billing_cycle is None
