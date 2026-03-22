"""Subscriptions controller — J9 (billing / plan management).

Exposes four endpoints:
  GET  /subscriptions/me       — current user subscription state (auth required)
  POST /subscriptions/checkout — create a checkout session      (auth required)
  POST /subscriptions/cancel   — cancel the subscription        (auth required)
  POST /subscriptions/webhook  — provider webhook               (no auth)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any
from uuid import UUID

from flask import Blueprint, current_app, jsonify, request
from flask.ctx import has_app_context
from flask.typing import ResponseReturnValue

from app.auth import get_active_auth_context
from app.extensions.database import db
from app.http.request_context import current_request_id
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.billing_adapter import BillingProvider, get_default_billing_provider
from app.services.subscription_service import (
    cancel_subscription,
    get_or_create_subscription,
    sync_subscription_from_provider,
)

logger = logging.getLogger(__name__)

subscription_bp = Blueprint("subscriptions", __name__, url_prefix="/subscriptions")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_FREE_PLAN_CODE = "free"


def _serialize_subscription(sub: Subscription) -> dict[str, Any]:
    return {
        "id": str(sub.id),
        "user_id": str(sub.user_id),
        "plan_code": sub.plan_code,
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


def _ok(data: dict[str, Any], status: int = 200) -> ResponseReturnValue:
    return jsonify({"success": True, "data": data}), status


def _err(message: str, code: str, status: int) -> ResponseReturnValue:
    return jsonify(
        {"success": False, "error": {"code": code, "message": message}}
    ), status


def _get_provider() -> BillingProvider:
    return get_default_billing_provider()


# ---------------------------------------------------------------------------
# GET /subscriptions/me
# ---------------------------------------------------------------------------


@subscription_bp.get("/me")
def get_my_subscription() -> ResponseReturnValue:
    """Return the authenticated user's current subscription state."""
    auth = get_active_auth_context()
    sub = get_or_create_subscription(UUID(auth.subject))
    provider = _get_provider()
    sub = sync_subscription_from_provider(sub, provider)
    return _ok({"subscription": _serialize_subscription(sub)})


# ---------------------------------------------------------------------------
# POST /subscriptions/checkout
# ---------------------------------------------------------------------------


@subscription_bp.post("/checkout")
def create_checkout_session() -> ResponseReturnValue:
    """Create a billing checkout session for the requested plan."""
    auth = get_active_auth_context()

    body: dict[str, Any] = request.get_json(silent=True) or {}
    plan_slug: str | None = body.get("plan_slug")
    if not plan_slug:
        return _err("plan_slug is required", "VALIDATION_ERROR", 400)

    provider = _get_provider()
    try:
        result = provider.create_checkout_session(
            user_id=str(UUID(auth.subject)), plan_slug=plan_slug
        )
    except Exception:
        current_app.logger.exception("Failed to create checkout session")
        return _err("Failed to create checkout session", "INTERNAL_ERROR", 500)

    return _ok(
        {
            "checkout_url": result.get("checkout_url"),
            "provider": result.get("provider"),
        },
        201,
    )


# ---------------------------------------------------------------------------
# POST /subscriptions/cancel
# ---------------------------------------------------------------------------


@subscription_bp.post("/cancel")
def cancel_my_subscription() -> ResponseReturnValue:
    """Cancel the authenticated user's subscription."""
    auth = get_active_auth_context()

    sub = get_or_create_subscription(UUID(auth.subject))
    if sub.status == SubscriptionStatus.CANCELED:
        return _err("Subscription is already canceled", "ALREADY_CANCELED", 409)

    provider = _get_provider()
    try:
        sub = cancel_subscription(sub, provider)
    except Exception:
        current_app.logger.exception("Failed to cancel subscription")
        return _err("Failed to cancel subscription", "INTERNAL_ERROR", 500)

    return _ok({"subscription": _serialize_subscription(sub)})


# ---------------------------------------------------------------------------
# POST /subscriptions/webhook
# ---------------------------------------------------------------------------

_WEBHOOK_SIGNATURE_HEADER = "X-Billing-Signature"
_WEBHOOK_SECRET_ENV = "BILLING_WEBHOOK_SECRET"
_WEBHOOK_ALLOW_UNSIGNED_ENV = "BILLING_WEBHOOK_ALLOW_UNSIGNED"


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _allow_unsigned_webhooks() -> bool:
    """Unsigned webhook traffic must be explicitly enabled per environment."""
    if not _read_bool_env(_WEBHOOK_ALLOW_UNSIGNED_ENV, default=False):
        return False
    if not has_app_context():
        return False
    if current_app.testing:
        return True

    runtime_env = (
        str(
            current_app.config.get("ENV")
            or current_app.config.get("FLASK_ENV")
            or current_app.config.get("APP_ENV")
            or os.getenv("FLASK_ENV")
            or os.getenv("APP_ENV")
            or os.getenv("AURAXIS_ENV")
            or ""
        )
        .strip()
        .lower()
    )
    return runtime_env in {"local", "test"}


def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 webhook signature.

    Default policy is fail-closed: missing ``BILLING_WEBHOOK_SECRET`` rejects
    requests unless the environment explicitly opts into unsigned webhooks.
    That keeps production strict while allowing deterministic local/test flows.
    """
    secret = os.getenv(_WEBHOOK_SECRET_ENV, "")
    if not secret:
        return _allow_unsigned_webhooks()
    if not signature:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@subscription_bp.post("/webhook")
def handle_webhook() -> ResponseReturnValue:
    """Receive provider webhook events.

    This endpoint intentionally has no JWT authentication — providers call it
    directly. Payload authenticity is validated via HMAC signature. Unsigned
    requests are only accepted when the environment explicitly enables them.

    Supported events
    ----------------
    subscription.activated   — set status to ACTIVE
    subscription.canceled    — set status to CANCELED
    subscription.past_due    — set status to PAST_DUE
    <any other event>        — 200 no-op
    """
    raw_body: bytes = request.get_data()
    signature = request.headers.get(_WEBHOOK_SIGNATURE_HEADER, "")

    if not _verify_webhook_signature(raw_body, signature):
        logger.warning(
            "Billing webhook invalid signature request_id=%s",
            current_request_id(),
        )
        return _err("Invalid signature", "UNAUTHORIZED", 401)

    payload: dict[str, Any] = request.get_json(silent=True) or {}
    event_type: str = payload.get("event", "")
    provider_subscription_id: str | None = payload.get("subscription_id")
    event_id: str | None = payload.get("event_id")

    # No-op for unknown events
    if event_type not in {
        "subscription.activated",
        "subscription.canceled",
        "subscription.past_due",
    }:
        logger.info("Unhandled billing webhook event: %s — ignoring", event_type)
        return _ok({"received": True, "processed": False})

    if not provider_subscription_id:
        return _err("subscription_id is required", "VALIDATION_ERROR", 400)

    sub: Subscription | None = Subscription.query.filter_by(
        provider_subscription_id=provider_subscription_id
    ).first()

    if sub is None:
        # Provider may send events for subscriptions we haven't recorded yet.
        # Accept and ignore gracefully.
        logger.warning(
            "Webhook %s for unknown provider_subscription_id=%s — ignoring",
            event_type,
            provider_subscription_id,
        )
        return _ok({"received": True, "processed": False})

    # Idempotency: skip already-processed events
    if event_id and sub.provider_event_id == event_id:
        return _ok({"received": True, "processed": False, "reason": "duplicate"})

    _STATUS_MAP = {
        "subscription.activated": SubscriptionStatus.ACTIVE,
        "subscription.canceled": SubscriptionStatus.CANCELED,
        "subscription.past_due": SubscriptionStatus.PAST_DUE,
    }
    sub.status = _STATUS_MAP[event_type]
    if event_id:
        sub.provider_event_id = event_id
    db.session.commit()

    return _ok({"received": True, "processed": True})


def register_subscription_dependencies(app: Any) -> None:  # noqa: ANN401
    """No-op dependency registration kept for symmetry with other controllers."""
