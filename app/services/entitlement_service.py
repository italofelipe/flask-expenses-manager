"""Entitlement service — J12 / H-PROD-01 (subscription state & entitlement enforcement).

Public surface
--------------
has_entitlement(user_id, feature_key) -> bool
require_entitlement(feature_key)       -> Flask decorator (403 on failure)
grant_entitlement(...)                 -> Entitlement
revoke_entitlement(user_id, feature_key) -> None
sync_entitlements_from_subscription(subscription) -> list[Entitlement]
activate_premium(user_id, expires_at) -> list[Entitlement]
deactivate_premium(user_id) -> None
check_access(user_id, feature) -> bool
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from flask import Response, jsonify
from flask_jwt_extended import verify_jwt_in_request

from app.config.plan_features import PLAN_FEATURES
from app.extensions.database import db
from app.models.entitlement import Entitlement, EntitlementSource
from app.models.subscription import Subscription, SubscriptionStatus
from app.utils.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core query
# ---------------------------------------------------------------------------


def has_entitlement(user_id: str | UUID, feature_key: str) -> bool:
    """Return True when *user_id* holds a non-expired entitlement for *feature_key*."""
    now = utc_now_naive()
    ent = (
        Entitlement.query.filter_by(
            user_id=user_id,
            feature_key=feature_key,
        )
        .filter((Entitlement.expires_at.is_(None)) | (Entitlement.expires_at > now))
        .first()
    )
    return ent is not None


# ---------------------------------------------------------------------------
# Flask route decorator
# ---------------------------------------------------------------------------


def require_entitlement(feature_key: str) -> Any:
    """Flask route decorator — returns 403 JSON when user lacks entitlement.

    Must be applied after ``@jwt_required()`` so that a valid JWT is already
    in scope.

    Example::

        @app.route("/export")
        @jwt_required()
        @require_entitlement("export_pdf")
        def export_pdf():
            ...
    """

    def decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            verify_jwt_in_request()
            from app.auth import current_user_id as _current_user_id

            uid = _current_user_id()
            if not has_entitlement(uid, feature_key):
                body: Response = jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "ENTITLEMENT_REQUIRED",
                            "message": (
                                f"Feature '{feature_key}' requires an active"
                                " entitlement."
                            ),
                        },
                    }
                )
                body.status_code = 403
                return body
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def grant_entitlement(
    user_id: str | UUID,
    feature_key: str,
    source: str,
    expires_at: datetime | None = None,
) -> Entitlement:
    """Create or update an entitlement for *(user_id, feature_key)*.

    If an entitlement already exists (regardless of expiry) it is updated in
    place rather than creating a duplicate row.
    """
    try:
        source_enum = EntitlementSource(source)
    except ValueError:
        source_enum = EntitlementSource.MANUAL

    existing = Entitlement.query.filter_by(
        user_id=user_id, feature_key=feature_key
    ).first()

    if existing is not None:
        existing.source = source_enum
        existing.expires_at = expires_at
        existing.granted_at = utc_now_naive()
        db.session.flush()
        return cast(Entitlement, existing)

    ent = Entitlement(
        user_id=user_id,
        feature_key=feature_key,
        source=source_enum,
        expires_at=expires_at,
    )
    db.session.add(ent)
    db.session.flush()
    return ent


def revoke_entitlement(user_id: str | UUID, feature_key: str) -> None:
    """Delete the entitlement row for *(user_id, feature_key)* if it exists."""
    Entitlement.query.filter_by(user_id=user_id, feature_key=feature_key).delete(
        synchronize_session="fetch"
    )
    db.session.flush()


# ---------------------------------------------------------------------------
# Subscription-driven sync
# ---------------------------------------------------------------------------


def sync_entitlements_from_subscription(
    subscription: Subscription,
) -> list[Entitlement]:
    """Grant/revoke feature entitlements driven by *subscription*.

    Rules
    -----
    - ``premium`` or ``trial`` plan → grant all PLAN_FEATURES entries.
    - ``free`` plan, or status in {CANCELED, EXPIRED, PAST_DUE} → revoke premium-only
      features, keep free-tier features.
    - Always normalises existing entitlements: unknown features for the plan
      are removed, missing ones are added.

    Returns the full list of active entitlements after the sync.
    """
    user_id = subscription.user_id
    plan_slug = subscription.plan_code or "free"
    status = subscription.status

    _DEGRADED_STATUSES = {
        SubscriptionStatus.CANCELED,
        SubscriptionStatus.EXPIRED,
        SubscriptionStatus.PAST_DUE,
    }

    # Determine effective plan based on status
    if status in _DEGRADED_STATUSES:
        effective_plan = "free"
    else:
        effective_plan = plan_slug if plan_slug in PLAN_FEATURES else "free"

    desired_features: set[str] = set(PLAN_FEATURES[effective_plan])

    # Determine source enum for granted entitlements
    if effective_plan == "trial" or status == SubscriptionStatus.TRIALING:
        source = EntitlementSource.TRIAL
    elif effective_plan in ("premium",):
        source = EntitlementSource.SUBSCRIPTION
    else:
        source = EntitlementSource.SUBSCRIPTION

    # Fetch current entitlements that were granted by subscription/trial sources
    # (manual entitlements are intentionally left untouched)
    managed_sources = {EntitlementSource.SUBSCRIPTION, EntitlementSource.TRIAL}
    existing: list[Entitlement] = Entitlement.query.filter(
        Entitlement.user_id == user_id,
        Entitlement.source.in_(managed_sources),
    ).all()

    existing_keys: set[str] = {e.feature_key for e in existing}

    # Revoke features no longer in the desired set
    for feature_key in existing_keys - desired_features:
        revoke_entitlement(user_id, feature_key)
        logger.info(
            "Revoked entitlement user=%s feature=%s (plan=%s status=%s)",
            user_id,
            feature_key,
            effective_plan,
            status.value if status else "unknown",
        )

    # Grant missing features
    for feature_key in desired_features - existing_keys:
        grant_entitlement(
            user_id=user_id,
            feature_key=feature_key,
            source=source.value,
            expires_at=subscription.current_period_end,
        )
        logger.info(
            "Granted entitlement user=%s feature=%s (plan=%s)",
            user_id,
            feature_key,
            effective_plan,
        )

    # Also update expires_at on already-existing managed entitlements
    for ent in existing:
        if ent.feature_key in desired_features:
            ent.expires_at = subscription.current_period_end
            ent.source = source

    db.session.flush()

    # Return full active list (managed + manual)
    return list(
        Entitlement.query.filter_by(user_id=user_id)
        .filter(
            (Entitlement.expires_at.is_(None))
            | (Entitlement.expires_at > utc_now_naive())
        )
        .all()
    )


# ---------------------------------------------------------------------------
# H-PROD-01 convenience wrappers (Asaas billing integration)
# ---------------------------------------------------------------------------


def activate_premium(
    user_id: str | UUID,
    expires_at: datetime | None = None,
) -> list[Entitlement]:
    """Grant all premium feature entitlements to *user_id*.

    Creates or refreshes each entitlement in PLAN_FEATURES["premium"].
    Returns the resulting list of active entitlements for the user.

    This is a convenience wrapper that does NOT require a Subscription record —
    useful for webhook-driven activation where we want to be resilient against
    missing subscription rows.
    """
    from app.config.plan_features import PLAN_FEATURES

    features = PLAN_FEATURES.get("premium", [])
    for feature_key in features:
        grant_entitlement(
            user_id=user_id,
            feature_key=feature_key,
            source=EntitlementSource.SUBSCRIPTION.value,
            expires_at=expires_at,
        )
    db.session.commit()

    now = utc_now_naive()
    return list(
        Entitlement.query.filter_by(user_id=user_id)
        .filter((Entitlement.expires_at.is_(None)) | (Entitlement.expires_at > now))
        .all()
    )


def deactivate_premium(user_id: str | UUID) -> None:
    """Revoke all premium-only feature entitlements for *user_id*.

    Free-tier features are left intact.  Commits the session.
    """
    from app.config.plan_features import PLAN_FEATURES, PREMIUM_FEATURES

    _ = PLAN_FEATURES  # imported for completeness; PREMIUM_FEATURES is the set we need
    for feature_key in PREMIUM_FEATURES:
        revoke_entitlement(user_id, feature_key)
    db.session.commit()


def check_access(user_id: str | UUID, feature: str) -> bool:
    """Return True when *user_id* may access *feature*.

    Checks both a live entitlement row *and* the trial window on the user's
    Subscription record, so callers do not need to join two tables.
    """
    if has_entitlement(user_id, feature):
        return True

    # Secondary check: active trial period on subscription record
    from app.models.subscription import Subscription, SubscriptionStatus

    now = utc_now_naive()
    sub: Subscription | None = Subscription.query.filter_by(user_id=user_id).first()
    if sub is None:
        return False
    if sub.status == SubscriptionStatus.TRIALING and sub.trial_ends_at is not None:
        return bool(sub.trial_ends_at > now)
    return False


# ---------------------------------------------------------------------------
# Legacy class-based API (kept for J7-1 compatibility)
# ---------------------------------------------------------------------------


class EntitlementService:
    """Thin wrapper retained for any existing callers from J7-1."""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    def list_entitlements(self) -> list[Entitlement]:
        now = utc_now_naive()
        return list(
            Entitlement.query.filter_by(user_id=self.user_id)
            .filter((Entitlement.expires_at.is_(None)) | (Entitlement.expires_at > now))
            .all()
        )

    def check_entitlement(self, feature_key: str) -> bool:
        return has_entitlement(self.user_id, feature_key)
