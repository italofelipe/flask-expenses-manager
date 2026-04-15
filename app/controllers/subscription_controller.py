"""Subscriptions controller — J9 (billing / plan management).

Exposes five endpoints:
  GET  /subscriptions/plans    — public billing plan catalog        (public)
  GET  /subscriptions/me       — current user subscription state (auth required)
  POST /subscriptions/checkout — create a checkout session      (auth required)
  POST /subscriptions/cancel   — cancel the subscription        (auth required)
  POST /subscriptions/webhook  — provider webhook               (no auth)
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue

from app.application.services.billing_email_service import dispatch_billing_email
from app.auth import get_active_auth_context, get_active_user
from app.config.billing_plans import (
    canonical_offer_slug,
    list_public_billing_plans,
    resolve_checkout_plan_offer,
)
from app.controllers.response_contract import compat_error_response
from app.controllers.subscription_webhook_payload import (
    _ASAAS_WEBHOOK_TOKEN_HEADER,
    _WEBHOOK_SIGNATURE_HEADER,
    _extract_subscription_identifiers,
    _find_subscription_for_snapshot,
    _is_supported_webhook_event,
    _is_webhook_request_authorized,
)
from app.controllers.subscription_webhook_payload import (
    _extract_event_id as _extract_event_id,  # re-export for billing_webhooks_cli
)
from app.controllers.subscription_webhook_payload import (
    _extract_provider_snapshot as _extract_provider_snapshot,  # re-export
)
from app.extensions.database import db
from app.http.request_context import current_request_id
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.models.webhook_event import WebhookEvent, WebhookEventStatus
from app.services.billing_adapter import (
    BillingCheckoutCustomer,
    BillingProvider,
    BillingProviderError,
    BillingSubscriptionSnapshot,
    get_default_billing_provider,
)
from app.services.subscription_service import (
    apply_subscription_snapshot,
    cancel_subscription,
    get_or_create_subscription,
    sync_subscription_from_provider,
)
from app.utils.datetime_utils import utc_now_naive
from app.utils.response_builder import json_response

logger = logging.getLogger(__name__)

subscription_bp = Blueprint("subscriptions", __name__, url_prefix="/subscriptions")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_FREE_PLAN_CODE = "free"
_CHECKOUT_SESSION_FAILURE_MESSAGE = "Failed to create checkout session"


def _serialize_subscription(sub: Subscription) -> dict[str, Any]:
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


def _ok(data: dict[str, Any], status: int = 200) -> ResponseReturnValue:
    return json_response({"success": True, "data": data}, status_code=status)


def _err(
    message: str,
    code: str,
    status: int,
    *,
    details: dict[str, Any] | None = None,
) -> ResponseReturnValue:
    return compat_error_response(
        legacy_payload={"success": False, "error": {"code": code, "message": message}},
        status_code=status,
        message=message,
        error_code=code,
        details=details,
    )


def _get_provider() -> BillingProvider:
    return get_default_billing_provider()


def _checkout_error(status_code: int, error_code: str) -> ResponseReturnValue:
    current_app.logger.exception(_CHECKOUT_SESSION_FAILURE_MESSAGE)
    return _err(_CHECKOUT_SESSION_FAILURE_MESSAGE, error_code, status_code)


# ---------------------------------------------------------------------------
# GET /subscriptions/plans
# ---------------------------------------------------------------------------


@subscription_bp.get("/plans")
def list_subscription_plans() -> ResponseReturnValue:
    """Return the public billing plan catalog for MVP1."""
    return _ok({"plans": list_public_billing_plans()})


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
    auth, user = get_active_user()

    body: dict[str, Any] = request.get_json(silent=True) or {}
    plan_slug: str | None = body.get("plan_slug")
    if not plan_slug:
        return _err("plan_slug is required", "VALIDATION_ERROR", 400)

    # Frontend clients send a plan-code-style slug ("pro") together with a
    # separate billing_cycle ("monthly"|"annual"). Compose the canonical alias
    # ("pro_monthly", "pro_annual") so resolve_checkout_plan_offer can find it
    # via legacy_aliases. Fall back to resolving plan_slug alone when
    # billing_cycle is absent (e.g. direct API calls using the full slug).
    billing_cycle_raw: str | None = (
        str(body.get("billing_cycle") or "").strip().lower() or None
    )
    if billing_cycle_raw:
        composed_slug = f"{plan_slug}_{billing_cycle_raw}"
        offer = resolve_checkout_plan_offer(
            composed_slug
        ) or resolve_checkout_plan_offer(plan_slug)
    else:
        offer = resolve_checkout_plan_offer(plan_slug)

    if offer is None:
        return _err("Unsupported plan_slug", "VALIDATION_ERROR", 400)

    provider = _get_provider()
    try:
        result = provider.create_checkout_session(
            customer=BillingCheckoutCustomer(
                user_id=str(UUID(auth.subject)),
                name=str(user.name),
                email=str(user.email),
            ),
            plan_slug=offer.slug,
        )
    except BillingProviderError:
        return _checkout_error(502, "UPSTREAM_ERROR")
    except Exception:
        return _checkout_error(500, "INTERNAL_ERROR")

    subscription = get_or_create_subscription(UUID(auth.subject))
    provider_name = str(result.get("provider") or "").strip()
    provider_customer_id = result.get("provider_customer_id")
    if provider_name:
        subscription.provider = provider_name
    if isinstance(provider_customer_id, str) and provider_customer_id.strip():
        subscription.provider_customer_id = provider_customer_id.strip()
    db.session.commit()

    return _ok(
        {
            "plan_slug": offer.slug,
            "plan_code": offer.plan_code,
            "billing_cycle": (
                offer.billing_cycle.value if offer.billing_cycle else None
            ),
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


def _process_webhook_snapshot(
    event_type: str,
    event_id: str | None,
    snapshot: BillingSubscriptionSnapshot,
    webhook_ev: WebhookEvent,
) -> ResponseReturnValue:
    subscription = _find_subscription_for_snapshot(snapshot)
    if subscription is None:
        logger.warning(
            "Webhook %s for unknown provider_subscription_id=%s — ignoring",
            event_type,
            snapshot.get("provider_id"),
        )
        webhook_ev.mark_skipped(reason="unknown_subscription")
        db.session.commit()
        return _ok({"received": True, "processed": False})

    if event_id and subscription.provider_event_id == event_id:
        webhook_ev.mark_skipped(reason="duplicate")
        db.session.commit()
        return _ok({"received": True, "processed": False, "reason": "duplicate"})

    if event_id:
        subscription.provider_event_id = event_id

    # Mark processed before the commit inside apply_subscription_snapshot.
    webhook_ev.mark_processed(now=utc_now_naive())
    apply_subscription_snapshot(subscription, snapshot)  # commits all session objects

    user = User.query.filter_by(id=subscription.user_id).first()
    if user is not None:
        try:
            dispatch_billing_email(
                user=user,
                subscription=subscription,
                event_type=event_type,
            )
        except Exception:
            logger.exception(
                "Failed to dispatch billing email for event=%s subscription_id=%s",
                event_type,
                str(subscription.id),
            )

    return _ok({"received": True, "processed": True})


@subscription_bp.post("/webhook")
def handle_webhook() -> ResponseReturnValue:
    """Receive provider webhook events.

    This endpoint intentionally has no JWT authentication — providers call it
    directly. Payload authenticity is validated via HMAC signature. Unsigned
    requests are only accepted when the environment explicitly enables them.

    Every request — authorised or not — is persisted to ``webhook_events`` for
    full auditability.  Failed events can be retried via the
    ``flask billing-webhooks retry-failed`` CLI command.

    Supported events
    ----------------
    subscription.activated   — set status to ACTIVE
    subscription.canceled    — set status to CANCELED
    subscription.past_due    — set status to PAST_DUE
    PAYMENT_RECEIVED         — set status to ACTIVE
    PAYMENT_CONFIRMED        — set status to ACTIVE
    PAYMENT_OVERDUE          — set status to PAST_DUE
    SUBSCRIPTION_DELETED     — set status to CANCELED
    <any other event>        — 200 no-op
    """
    raw_body: bytes = request.get_data()
    signature = request.headers.get(_WEBHOOK_SIGNATURE_HEADER, "")
    asaas_token = request.headers.get(_ASAAS_WEBHOOK_TOKEN_HEADER, "")
    sig_verified = _is_webhook_request_authorized(raw_body, signature, asaas_token)

    payload: dict[str, Any] = request.get_json(silent=True) or {}
    event_type: str = payload.get("event", "")
    event_id = _extract_event_id(payload)

    # Best-effort identifier extraction for the audit record.
    try:
        (
            provider_subscription_id,
            provider_customer_id,
            *_,
        ) = _extract_subscription_identifiers(payload)
    except Exception:
        provider_subscription_id = None
        provider_customer_id = None

    # Persist audit record before any processing — capture every attempt.
    now = utc_now_naive()
    raw_text = raw_body.decode("utf-8", errors="replace")[:50_000]
    webhook_ev = WebhookEvent(
        event_id=event_id,
        event_type=event_type or "unknown",
        provider="asaas",
        provider_subscription_id=provider_subscription_id,
        provider_customer_id=provider_customer_id,
        raw_payload=raw_text,
        signature_verified=sig_verified,
        received_at=now,
        status=WebhookEventStatus.RECEIVED.value,
    )
    db.session.add(webhook_ev)

    if not sig_verified:
        webhook_ev.mark_skipped(reason="invalid_signature")
        db.session.commit()
        logger.warning(
            "Billing webhook invalid signature request_id=%s",
            current_request_id(),
        )
        return _err(
            "Invalid signature",
            "UNAUTHORIZED",
            401,
            details={"request_id": current_request_id()},
        )

    if not _is_supported_webhook_event(event_type):
        webhook_ev.mark_skipped(reason=f"unsupported_event:{event_type}")
        db.session.commit()
        logger.info("Unhandled billing webhook event: %s — ignoring", event_type)
        return _ok({"received": True, "processed": False})

    snapshot = _extract_provider_snapshot(payload)
    if snapshot is None:
        webhook_ev.mark_skipped(reason="unresolvable_subscription")
        db.session.commit()
        return _err(
            "Unable to resolve subscription from webhook payload",
            "VALIDATION_ERROR",
            400,
        )

    try:
        return _process_webhook_snapshot(event_type, event_id, snapshot, webhook_ev)
    except Exception as exc:
        webhook_ev.mark_failed(reason=str(exc), now=utc_now_naive())
        db.session.commit()
        raise


def register_subscription_dependencies(app: Any) -> None:  # noqa: ANN401
    """No-op dependency registration kept for symmetry with other controllers."""
