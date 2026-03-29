"""Tests for J9 — billing provider adapter and subscription state endpoints."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Dict
from unittest.mock import MagicMock

from app.models.subscription import BillingCycle, Subscription, SubscriptionStatus
from app.services.billing_adapter import BillingProvider, StubBillingProvider
from app.services.subscription_service import (
    cancel_subscription,
    get_or_create_subscription,
    sync_subscription_from_provider,
)

# ---------------------------------------------------------------------------
# Helpers shared by controller tests
# ---------------------------------------------------------------------------


def _register_and_login(client, *, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    r = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201

    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.get_json()["token"]


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# StubBillingProvider unit tests
# ---------------------------------------------------------------------------


class TestStubBillingProvider:
    def setup_method(self) -> None:
        self.provider = StubBillingProvider()

    def test_implements_protocol(self) -> None:
        assert isinstance(self.provider, BillingProvider)

    def test_get_subscription_returns_active_status(self) -> None:
        result = self.provider.get_subscription("sub_123")
        assert result["status"] == "active"
        assert result["provider_id"] == "sub_123"
        assert result["provider"] == "stub"

    def test_cancel_subscription_returns_canceled_status(self) -> None:
        result = self.provider.cancel_subscription("sub_123")
        assert result["status"] == "canceled"
        assert result["provider"] == "stub"

    def test_create_checkout_session_returns_url(self) -> None:
        result = self.provider.create_checkout_session("user_abc", "premium_monthly")
        assert "checkout_url" in result
        assert "premium_monthly" in result["checkout_url"]
        assert result["provider"] == "stub"


# ---------------------------------------------------------------------------
# Subscription service unit tests
# ---------------------------------------------------------------------------


class TestSubscriptionService:
    def test_get_or_create_creates_free_subscription(self, app) -> None:
        user_id = uuid.uuid4()
        with app.app_context():
            sub = get_or_create_subscription(user_id)
            assert sub.user_id == user_id
            assert sub.plan_code == "free"
            assert sub.status == SubscriptionStatus.FREE

    def test_get_or_create_returns_existing_subscription(self, app) -> None:
        user_id = uuid.uuid4()
        with app.app_context():
            sub1 = get_or_create_subscription(user_id)
            sub2 = get_or_create_subscription(user_id)
            assert sub1.id == sub2.id

    def test_sync_skips_when_no_provider_id(self, app) -> None:
        user_id = uuid.uuid4()
        provider = StubBillingProvider()
        with app.app_context():
            sub = get_or_create_subscription(user_id)
            assert sub.provider_subscription_id is None
            synced = sync_subscription_from_provider(sub, provider)
            # Status unchanged — no provider ID means nothing to sync
            assert synced.status == SubscriptionStatus.FREE

    def test_sync_updates_status_from_provider(self, app) -> None:
        user_id = uuid.uuid4()
        mock_provider = MagicMock()
        mock_provider.get_subscription.return_value = {
            "status": "active",
            "plan_code": "premium",
            "offer_code": "premium_monthly",
            "billing_cycle": "monthly",
        }
        with app.app_context():
            from app.extensions.database import db

            sub = get_or_create_subscription(user_id)
            sub.provider_subscription_id = "sub_xyz"
            db.session.commit()

            synced = sync_subscription_from_provider(sub, mock_provider)
            assert synced.status == SubscriptionStatus.ACTIVE
            assert synced.plan_code == "premium"
            assert synced.billing_cycle == BillingCycle.MONTHLY
            mock_provider.get_subscription.assert_called_once_with("sub_xyz")

    def test_cancel_sets_canceled_status(self, app) -> None:
        user_id = uuid.uuid4()
        with app.app_context():
            sub = get_or_create_subscription(user_id)
            provider = StubBillingProvider()
            canceled = cancel_subscription(sub, provider)
            assert canceled.status == SubscriptionStatus.CANCELED

    def test_cancel_calls_provider_when_provider_id_present(self, app) -> None:
        user_id = uuid.uuid4()
        mock_provider = MagicMock()
        mock_provider.cancel_subscription.return_value = {"status": "canceled"}
        with app.app_context():
            from app.extensions.database import db

            sub = get_or_create_subscription(user_id)
            sub.provider_subscription_id = "sub_abc"
            db.session.commit()

            cancel_subscription(sub, mock_provider)
            mock_provider.cancel_subscription.assert_called_once_with("sub_abc")


# ---------------------------------------------------------------------------
# Subscription controller endpoint tests
# ---------------------------------------------------------------------------


class TestGetMySubscription:
    def test_get_plans_returns_public_catalog(self, client) -> None:
        resp = client.get("/subscriptions/plans")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        plans = body["data"]["plans"]
        assert len(plans) == 3
        assert plans[0]["slug"] == "free"
        assert plans[1]["slug"] == "premium_monthly"
        assert plans[2]["slug"] == "premium_annual"

    def test_get_subscription_no_prior_record_returns_free(self, client) -> None:
        """GET /subscriptions/me — returns free defaults when no subscription exists."""
        token = _register_and_login(client, prefix="sub-get")
        resp = client.get("/subscriptions/me", headers=_auth_headers(token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        sub = body["data"]["subscription"]
        assert sub["plan_code"] == "free"
        assert sub["status"] == "free"

    def test_get_subscription_returns_401_without_token(self, client) -> None:
        resp = client.get("/subscriptions/me")
        assert resp.status_code == 401

    def test_get_subscription_active_returns_data(self, client, app) -> None:
        """GET /subscriptions/me when subscription exists — returns correct data."""
        token = _register_and_login(client, prefix="sub-active")

        # Trigger record creation first
        resp0 = client.get("/subscriptions/me", headers=_auth_headers(token))
        assert resp0.status_code == 200
        sub_id = resp0.get_json()["data"]["subscription"]["id"]

        # Patch status directly in the DB
        with app.app_context():
            from app.extensions.database import db

            sub: Subscription = Subscription.query.filter_by(
                id=uuid.UUID(sub_id)
            ).first()  # type: ignore[assignment]
            sub.status = SubscriptionStatus.ACTIVE
            sub.plan_code = "premium"
            sub.billing_cycle = BillingCycle.MONTHLY
            db.session.commit()

        resp = client.get("/subscriptions/me", headers=_auth_headers(token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["subscription"]["status"] == "active"
        assert body["data"]["subscription"]["plan_code"] == "premium"
        assert body["data"]["subscription"]["offer_code"] == "premium_monthly"
        assert body["data"]["subscription"]["billing_cycle"] == "monthly"


class TestCreateCheckoutSession:
    def test_checkout_returns_checkout_url(self, client) -> None:
        token = _register_and_login(client, prefix="sub-checkout")
        resp = client.post(
            "/subscriptions/checkout",
            json={"plan_slug": "premium_monthly"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["success"] is True
        assert "checkout_url" in body["data"]
        assert body["data"]["plan_slug"] == "premium_monthly"
        assert body["data"]["plan_code"] == "premium"
        assert body["data"]["billing_cycle"] == "monthly"
        assert "premium_monthly" in body["data"]["checkout_url"]

    def test_checkout_legacy_alias_is_normalized(self, client) -> None:
        token = _register_and_login(client, prefix="sub-checkout-legacy")
        resp = client.post(
            "/subscriptions/checkout",
            json={"plan_slug": "pro_monthly"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["plan_slug"] == "premium_monthly"

    def test_checkout_unknown_plan_slug_returns_400(self, client) -> None:
        token = _register_and_login(client, prefix="sub-checkout-unknown")
        resp = client.post(
            "/subscriptions/checkout",
            json={"plan_slug": "invalid-plan"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_checkout_missing_plan_slug_returns_400(self, client) -> None:
        token = _register_and_login(client, prefix="sub-checkout-err")
        resp = client.post(
            "/subscriptions/checkout",
            json={},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_checkout_requires_auth(self, client) -> None:
        resp = client.post("/subscriptions/checkout", json={"plan_slug": "pro_monthly"})
        assert resp.status_code == 401


class TestCancelSubscription:
    def test_cancel_sets_status_canceled(self, client) -> None:
        token = _register_and_login(client, prefix="sub-cancel")
        # Ensure subscription exists first
        client.get("/subscriptions/me", headers=_auth_headers(token))

        resp = client.post("/subscriptions/cancel", headers=_auth_headers(token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["subscription"]["status"] == "canceled"

    def test_cancel_already_canceled_returns_409(self, client) -> None:
        token = _register_and_login(client, prefix="sub-cancel2")
        client.get("/subscriptions/me", headers=_auth_headers(token))
        # First cancel
        client.post("/subscriptions/cancel", headers=_auth_headers(token))
        # Second cancel
        resp = client.post("/subscriptions/cancel", headers=_auth_headers(token))
        assert resp.status_code == 409

    def test_cancel_requires_auth(self, client) -> None:
        resp = client.post("/subscriptions/cancel")
        assert resp.status_code == 401


class TestWebhook:
    def test_unknown_event_returns_200_noop(self, client) -> None:
        resp = client.post(
            "/subscriptions/webhook",
            json={"event": "unknown.event", "subscription_id": "sub_xyz"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["received"] is True
        assert body["data"]["processed"] is False

    def test_empty_payload_returns_200_noop(self, client) -> None:
        resp = client.post("/subscriptions/webhook", json={})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["processed"] is False

    def test_webhook_no_auth_header_accepted(self, client) -> None:
        """Webhook must NOT require JWT — providers call it without tokens."""
        resp = client.post(
            "/subscriptions/webhook",
            json={"event": "unknown.event.no_auth_check"},
        )
        assert resp.status_code == 200

    def test_webhook_known_event_unknown_subscription_returns_200(self, client) -> None:
        resp = client.post(
            "/subscriptions/webhook",
            json={
                "event": "subscription.activated",
                "subscription_id": "nonexistent_sub",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["processed"] is False

    def test_webhook_updates_subscription_status(self, client, app) -> None:
        token = _register_and_login(client, prefix="sub-wh")
        # Ensure subscription exists and capture its ID
        r = client.get("/subscriptions/me", headers=_auth_headers(token))
        sub_id = r.get_json()["data"]["subscription"]["id"]

        with app.app_context():
            from app.extensions.database import db

            sub: Subscription = Subscription.query.filter_by(
                id=uuid.UUID(sub_id)
            ).first()  # type: ignore[assignment]
            sub.provider_subscription_id = "sub_webhook_test"
            db.session.commit()

        resp = client.post(
            "/subscriptions/webhook",
            json={
                "event": "subscription.canceled",
                "subscription_id": "sub_webhook_test",
                "event_id": "evt_001",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["processed"] is True

        with app.app_context():
            sub_updated: Subscription = Subscription.query.filter_by(
                id=uuid.UUID(sub_id)
            ).first()  # type: ignore[assignment]
            assert sub_updated.status == SubscriptionStatus.CANCELED
            assert sub_updated.provider_event_id == "evt_001"

    def test_webhook_idempotency_skips_duplicate_event(self, client, app) -> None:
        token = _register_and_login(client, prefix="sub-wh-idem")
        r = client.get("/subscriptions/me", headers=_auth_headers(token))
        sub_id = r.get_json()["data"]["subscription"]["id"]

        with app.app_context():
            from app.extensions.database import db

            sub: Subscription = Subscription.query.filter_by(
                id=uuid.UUID(sub_id)
            ).first()  # type: ignore[assignment]
            sub.provider_subscription_id = "sub_idem"
            sub.provider_event_id = "evt_already_seen"
            db.session.commit()

        resp = client.post(
            "/subscriptions/webhook",
            json={
                "event": "subscription.canceled",
                "subscription_id": "sub_idem",
                "event_id": "evt_already_seen",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"].get("reason") == "duplicate"
        assert body["data"]["processed"] is False

    def test_webhook_rejects_unsigned_requests_when_explicitly_hardened(
        self,
        client,
        monkeypatch,
    ) -> None:
        monkeypatch.delenv("BILLING_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("BILLING_WEBHOOK_ALLOW_UNSIGNED", "false")

        resp = client.post(
            "/subscriptions/webhook",
            json={"event": "unknown.event", "subscription_id": "sub_xyz"},
        )

        assert resp.status_code == 401
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_webhook_rejects_unsigned_requests_outside_local_or_test_env(
        self,
        client,
        monkeypatch,
    ) -> None:
        monkeypatch.delenv("BILLING_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("BILLING_WEBHOOK_ALLOW_UNSIGNED", "true")
        monkeypatch.setenv("APP_ENV", "dev")

        original_testing = client.application.testing
        client.application.testing = False
        try:
            resp = client.post(
                "/subscriptions/webhook",
                json={"event": "unknown.event", "subscription_id": "sub_xyz"},
            )
        finally:
            client.application.testing = original_testing

        assert resp.status_code == 401
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_webhook_accepts_valid_signature_when_secret_is_configured(
        self,
        client,
        monkeypatch,
    ) -> None:
        secret = "billing-webhook-secret"
        monkeypatch.setenv("BILLING_WEBHOOK_SECRET", secret)
        monkeypatch.setenv("BILLING_WEBHOOK_ALLOW_UNSIGNED", "false")

        raw_body = b'{"event":"unknown.event","subscription_id":"sub_xyz"}'
        signature = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

        resp = client.post(
            "/subscriptions/webhook",
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Billing-Signature": signature,
            },
        )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["received"] is True
        assert body["data"]["processed"] is False

    def test_webhook_rejects_invalid_signature_when_secret_is_configured(
        self,
        client,
        monkeypatch,
    ) -> None:
        monkeypatch.setenv("BILLING_WEBHOOK_SECRET", "billing-webhook-secret")
        monkeypatch.setenv("BILLING_WEBHOOK_ALLOW_UNSIGNED", "false")

        resp = client.post(
            "/subscriptions/webhook",
            json={"event": "unknown.event", "subscription_id": "sub_xyz"},
            headers={"X-Billing-Signature": "invalid-signature"},
        )

        assert resp.status_code == 401
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_webhook_logs_warning_for_invalid_signature(
        self,
        client,
        monkeypatch,
        caplog,
    ) -> None:
        monkeypatch.setenv("BILLING_WEBHOOK_SECRET", "billing-webhook-secret")
        monkeypatch.setenv("BILLING_WEBHOOK_ALLOW_UNSIGNED", "false")

        with caplog.at_level(logging.WARNING):
            resp = client.post(
                "/subscriptions/webhook",
                json={"event": "unknown.event", "subscription_id": "sub_xyz"},
                headers={"X-Billing-Signature": "invalid-signature"},
            )

        assert resp.status_code == 401
        logs = [
            record.message
            for record in caplog.records
            if "Billing webhook invalid signature" in record.message
        ]
        assert len(logs) == 1
        assert "request_id=" in logs[0]
