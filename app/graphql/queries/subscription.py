"""GraphQL queries for Subscription/Billing domain (#835).

Mirrors REST endpoints:
  GET /subscriptions/plans → billingPlans
  GET /subscriptions/me   → mySubscription
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import graphene

from app.config.billing_plans import list_public_billing_plans
from app.graphql.auth import get_current_user_required
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_VALIDATION,
    build_public_graphql_error,
)
from app.graphql.types import (
    BillingPlanListPayloadType,
    BillingPlanType,
    SubscriptionType,
)
from app.services.billing_adapter import (
    BillingProviderError,
    get_default_billing_provider,
)
from app.services.subscription_service import (
    get_or_create_subscription,
    sync_subscription_from_provider,
)


def _to_billing_plan_type(data: Any) -> BillingPlanType:
    return BillingPlanType(
        slug=data["slug"],
        plan_code=data["plan_code"],
        display_name=data["display_name"],
        description=data["description"],
        price_cents=data["price_cents"],
        currency=data["currency"],
        billing_cycle=data["billing_cycle"] or "",
        is_active=data.get("checkout_enabled", True),
        features=[],
    )


def _to_subscription_type(data: dict[str, Any]) -> SubscriptionType:
    return SubscriptionType(
        id=data["id"],
        plan_code=data["plan_code"],
        offer_code=data.get("offer_code"),
        status=data["status"],
        billing_cycle=data.get("billing_cycle"),
        provider=data.get("provider"),
        provider_subscription_id=data.get("provider_subscription_id"),
        trial_ends_at=data.get("trial_ends_at"),
        current_period_start=data.get("current_period_start"),
        current_period_end=data.get("current_period_end"),
        canceled_at=data.get("canceled_at"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )


def _serialize_subscription(sub: Any) -> dict[str, Any]:
    from app.config.billing_plans import canonical_offer_slug

    offer_code = canonical_offer_slug(
        getattr(sub, "plan_code", None),
        getattr(sub, "billing_cycle", None),
    )
    billing_cycle = getattr(sub, "billing_cycle", None)
    trial_ends_at = getattr(sub, "trial_ends_at", None)
    current_period_start = getattr(sub, "current_period_start", None)
    current_period_end = getattr(sub, "current_period_end", None)
    canceled_at = getattr(sub, "canceled_at", None)
    created_at = getattr(sub, "created_at", None)
    updated_at = getattr(sub, "updated_at", None)
    status = getattr(sub, "status", None)
    return {
        "id": str(getattr(sub, "id", "")),
        "plan_code": getattr(sub, "plan_code", ""),
        "offer_code": offer_code,
        "status": status.value
        if status is not None and hasattr(status, "value")
        else str(status or ""),
        "billing_cycle": billing_cycle.value
        if billing_cycle is not None and hasattr(billing_cycle, "value")
        else billing_cycle,
        "provider": getattr(sub, "provider", None),
        "provider_subscription_id": getattr(sub, "provider_subscription_id", None),
        "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
        "current_period_start": current_period_start.isoformat()
        if current_period_start
        else None,
        "current_period_end": current_period_end.isoformat()
        if current_period_end
        else None,
        "canceled_at": canceled_at.isoformat() if canceled_at else None,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


class SubscriptionQueryMixin:
    billing_plans = graphene.Field(BillingPlanListPayloadType)
    my_subscription = graphene.Field(SubscriptionType)

    def resolve_billing_plans(
        self, _info: graphene.ResolveInfo
    ) -> BillingPlanListPayloadType:
        plans_data = list_public_billing_plans()
        plans = [_to_billing_plan_type(p) for p in plans_data]
        return BillingPlanListPayloadType(plans=plans)

    def resolve_my_subscription(self, _info: graphene.ResolveInfo) -> SubscriptionType:
        user = get_current_user_required()
        sub = get_or_create_subscription(UUID(str(user.id)))
        try:
            provider = get_default_billing_provider()
            sub = sync_subscription_from_provider(sub, provider)
        except BillingProviderError:
            pass
        except Exception as exc:
            raise build_public_graphql_error(
                "Erro ao sincronizar assinatura", code=GRAPHQL_ERROR_CODE_VALIDATION
            ) from exc
        return _to_subscription_type(_serialize_subscription(sub))
