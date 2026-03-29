"""Subscriptions controller — J9 (billing / plan management).

Exposes five endpoints:
  GET  /subscriptions/plans    — public billing plan catalog        (public)
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
from datetime import datetime
from typing import Any
from uuid import UUID

from flask import Blueprint, current_app, jsonify, request
from flask.ctx import has_app_context
from flask.typing import ResponseReturnValue

from app.application.services.billing_email_service import dispatch_billing_email
from app.auth import get_active_auth_context, get_active_user
from app.config.billing_plans import (
    canonical_offer_slug,
    list_public_billing_plans,
    resolve_checkout_plan_offer,
)
from app.controllers.response_contract import compat_error_response
from app.extensions.database import db
from app.http.request_context import current_request_id
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
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

logger = logging.getLogger(__name__)

subscription_bp = Blueprint("subscriptions", __name__, url_prefix="/subscriptions")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_FREE_PLAN_CODE = "free"
_CHECKOUT_SESSION_FAILURE_MESSAGE = "Failed to create checkout session"
_SUPPORTED_WEBHOOK_EVENTS = {
    "subscription.activated",
    "subscription.canceled",
    "subscription.past_due",
    "PAYMENT_RECEIVED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_OVERDUE",
    "SUBSCRIPTION_DELETED",
}


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
    return jsonify({"success": True, "data": data}), status


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

_WEBHOOK_SIGNATURE_HEADER = "X-Billing-Signature"
_ASAAS_WEBHOOK_TOKEN_HEADER = "asaas-access-token"
_WEBHOOK_SECRET_ENV = "BILLING_WEBHOOK_SECRET"
_WEBHOOK_ALLOW_UNSIGNED_ENV = "BILLING_WEBHOOK_ALLOW_UNSIGNED"
_ASAAS_WEBHOOK_TOKEN_ENV = "BILLING_ASAAS_WEBHOOK_TOKEN"


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


def _verify_asaas_webhook_token(header_value: str) -> bool:
    expected = os.getenv(_ASAAS_WEBHOOK_TOKEN_ENV, "").strip()
    if not expected:
        return False
    if not header_value.strip():
        return False
    return hmac.compare_digest(expected, header_value.strip())


def _is_webhook_request_authorized(
    payload: bytes, signature: str, asaas_token: str
) -> bool:
    return _verify_webhook_signature(payload, signature) or _verify_asaas_webhook_token(
        asaas_token
    )


def _extract_event_id(payload: dict[str, Any]) -> str | None:
    for key in ("event_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_offer_from_external_reference(
    external_reference: str | None,
) -> dict[str, str | None]:
    raw_reference = str(external_reference or "").strip()
    if not raw_reference:
        return {
            "plan_code": None,
            "offer_code": None,
            "billing_cycle": None,
        }

    offer = resolve_checkout_plan_offer(raw_reference.split(":")[-1])
    if offer is None:
        return {
            "plan_code": None,
            "offer_code": None,
            "billing_cycle": None,
        }
    return {
        "plan_code": offer.plan_code,
        "offer_code": offer.slug,
        "billing_cycle": (offer.billing_cycle.value if offer.billing_cycle else None),
    }


def _coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    for candidate in (normalized, normalized.replace("+0000", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _clean_optional_string(value: object) -> str | None:
    return str(value or "").strip() or None


def _extract_identifiers_from_subscription_object(
    subscription_object: dict[str, Any],
) -> tuple[str | None, str | None, str | None, object, object]:
    return (
        _clean_optional_string(subscription_object.get("id")),
        _clean_optional_string(subscription_object.get("customer")),
        _clean_optional_string(subscription_object.get("externalReference")),
        subscription_object.get("dateCreated"),
        subscription_object.get("nextDueDate"),
    )


def _merge_identifiers_from_payment_object(
    provider_subscription_id: str | None,
    provider_customer_id: str | None,
    external_reference: str | None,
    current_period_end: object,
    payment_object: dict[str, Any],
) -> tuple[str | None, str | None, str | None, object]:
    return (
        _clean_optional_string(payment_object.get("subscription"))
        or provider_subscription_id,
        _clean_optional_string(payment_object.get("customer")) or provider_customer_id,
        _clean_optional_string(payment_object.get("externalReference"))
        or external_reference,
        payment_object.get("dueDate") or current_period_end,
    )


def _merge_customer_from_checkout_object(
    provider_customer_id: str | None,
    checkout_object: dict[str, Any],
) -> str | None:
    return (
        _clean_optional_string(checkout_object.get("customer")) or provider_customer_id
    )


def _extract_subscription_identifiers(
    payload: dict[str, Any],
) -> tuple[str | None, str | None, str | None, Any, Any]:
    provider_subscription_id: str | None = None
    provider_customer_id: str | None = None
    external_reference: str | None = None
    current_period_start: object | None = None
    current_period_end: object | None = None

    subscription_object = payload.get("subscription")
    payment_object = payload.get("payment")
    checkout_object = payload.get("checkout")

    if isinstance(subscription_object, dict):
        (
            provider_subscription_id,
            provider_customer_id,
            external_reference,
            current_period_start,
            current_period_end,
        ) = _extract_identifiers_from_subscription_object(subscription_object)

    if isinstance(payment_object, dict):
        (
            provider_subscription_id,
            provider_customer_id,
            external_reference,
            current_period_end,
        ) = _merge_identifiers_from_payment_object(
            provider_subscription_id,
            provider_customer_id,
            external_reference,
            current_period_end,
            payment_object,
        )

    if isinstance(checkout_object, dict):
        provider_customer_id = _merge_customer_from_checkout_object(
            provider_customer_id,
            checkout_object,
        )

    legacy_subscription_id = _clean_optional_string(payload.get("subscription_id"))
    provider_subscription_id = provider_subscription_id or legacy_subscription_id
    return (
        provider_subscription_id,
        provider_customer_id,
        external_reference,
        _coerce_datetime(current_period_start),
        _coerce_datetime(current_period_end),
    )


def _resolve_status(event_type: str) -> str | None:
    status_map = {
        "subscription.activated": SubscriptionStatus.ACTIVE.value,
        "subscription.canceled": SubscriptionStatus.CANCELED.value,
        "subscription.past_due": SubscriptionStatus.PAST_DUE.value,
        "PAYMENT_RECEIVED": SubscriptionStatus.ACTIVE.value,
        "PAYMENT_CONFIRMED": SubscriptionStatus.ACTIVE.value,
        "PAYMENT_OVERDUE": SubscriptionStatus.PAST_DUE.value,
        "SUBSCRIPTION_DELETED": SubscriptionStatus.CANCELED.value,
    }
    return status_map.get(event_type)


def _extract_provider_snapshot(
    payload: dict[str, Any],
) -> BillingSubscriptionSnapshot | None:
    event_type = str(payload.get("event") or "").strip()
    (
        provider_subscription_id,
        provider_customer_id,
        external_reference,
        current_period_start,
        current_period_end,
    ) = _extract_subscription_identifiers(payload)

    if not provider_customer_id and not provider_subscription_id:
        return None

    status = _resolve_status(event_type)
    if status is None:
        return None

    offer_metadata = _resolve_offer_from_external_reference(external_reference)
    snapshot: BillingSubscriptionSnapshot = {
        "status": status,
        "provider_customer_id": provider_customer_id,
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
    }
    if event_type.isupper():
        snapshot["provider"] = "asaas"
    if provider_subscription_id:
        snapshot["provider_id"] = provider_subscription_id
    if offer_metadata["plan_code"]:
        snapshot["plan_code"] = offer_metadata["plan_code"]
    if offer_metadata["offer_code"]:
        snapshot["offer_code"] = offer_metadata["offer_code"]
    if offer_metadata["billing_cycle"]:
        snapshot["billing_cycle"] = offer_metadata["billing_cycle"]
    return snapshot


def _is_supported_webhook_event(event_type: str) -> bool:
    return event_type in _SUPPORTED_WEBHOOK_EVENTS


def _find_subscription_for_snapshot(
    snapshot: BillingSubscriptionSnapshot,
) -> Subscription | None:
    provider_subscription_id = snapshot.get("provider_id")
    if provider_subscription_id:
        subscription: Subscription | None = Subscription.query.filter_by(
            provider_subscription_id=provider_subscription_id
        ).first()
        if subscription is not None:
            return subscription

    provider_customer_id = snapshot.get("provider_customer_id")
    if provider_customer_id:
        subscription = Subscription.query.filter_by(
            provider_customer_id=provider_customer_id
        ).first()
        return subscription

    return None


def _process_webhook_snapshot(
    event_type: str,
    event_id: str | None,
    snapshot: BillingSubscriptionSnapshot,
) -> ResponseReturnValue:
    subscription = _find_subscription_for_snapshot(snapshot)
    if subscription is None:
        logger.warning(
            "Webhook %s for unknown provider_subscription_id=%s — ignoring",
            event_type,
            snapshot.get("provider_id"),
        )
        return _ok({"received": True, "processed": False})

    if event_id and subscription.provider_event_id == event_id:
        return _ok({"received": True, "processed": False, "reason": "duplicate"})

    if event_id:
        subscription.provider_event_id = event_id
    apply_subscription_snapshot(subscription, snapshot)

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

    Supported events
    ----------------
    subscription.activated   — set status to ACTIVE
    subscription.canceled    — set status to CANCELED
    subscription.past_due    — set status to PAST_DUE
    <any other event>        — 200 no-op
    """
    raw_body: bytes = request.get_data()
    signature = request.headers.get(_WEBHOOK_SIGNATURE_HEADER, "")
    asaas_token = request.headers.get(_ASAAS_WEBHOOK_TOKEN_HEADER, "")

    if not _is_webhook_request_authorized(raw_body, signature, asaas_token):
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

    payload: dict[str, Any] = request.get_json(silent=True) or {}
    event_type: str = payload.get("event", "")
    event_id = _extract_event_id(payload)
    snapshot = _extract_provider_snapshot(payload)

    if not _is_supported_webhook_event(event_type):
        logger.info("Unhandled billing webhook event: %s — ignoring", event_type)
        return _ok({"received": True, "processed": False})

    if snapshot is None:
        return _err(
            "Unable to resolve subscription from webhook payload",
            "VALIDATION_ERROR",
            400,
        )

    return _process_webhook_snapshot(event_type, event_id, snapshot)


def register_subscription_dependencies(app: Any) -> None:  # noqa: ANN401
    """No-op dependency registration kept for symmetry with other controllers."""
