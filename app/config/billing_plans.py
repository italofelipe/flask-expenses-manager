"""Canonical billing plan catalog for MVP1 monetization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from app.models.subscription import BillingCycle


class BillingPlanPayload(TypedDict):
    slug: str
    plan_code: str
    tier: str
    billing_cycle: str | None
    display_name: str
    description: str
    price_cents: int
    currency: str
    trial_days: int
    checkout_enabled: bool
    highlighted: bool


@dataclass(frozen=True)
class BillingPlanOffer:
    slug: str
    plan_code: str
    tier: str
    display_name: str
    description: str
    price_cents: int
    billing_cycle: BillingCycle | None = None
    currency: str = "BRL"
    trial_days: int = 0
    checkout_enabled: bool = True
    highlighted: bool = False
    legacy_aliases: tuple[str, ...] = ()


FREE_PLAN = BillingPlanOffer(
    slug="free",
    plan_code="free",
    tier="free",
    display_name="Free",
    description="Controle financeiro essencial e simulacoes basicas.",
    price_cents=0,
    billing_cycle=None,
    trial_days=0,
    checkout_enabled=False,
)

PREMIUM_MONTHLY_PLAN = BillingPlanOffer(
    slug="premium_monthly",
    plan_code="premium",
    tier="premium",
    display_name="Premium Mensal",
    description="Analises com IA, alertas e briefing semanal.",
    # DEC-168: R$27,90/mês — founder-confirmed 2026-04-05
    # Canonical: docs/wiki/MVP-1-Monetizacao-e-Assinaturas.md
    price_cents=2790,
    billing_cycle=BillingCycle.MONTHLY,
    trial_days=7,
    highlighted=True,
    legacy_aliases=("pro_monthly",),
)

PREMIUM_ANNUAL_PLAN = BillingPlanOffer(
    slug="premium_annual",
    plan_code="premium",
    tier="premium",
    display_name="Premium Anual",
    description="Mesmo pacote premium com desconto anual.",
    # DEC-168: R$220,00/ano (equiv. R$18,33/mês, 34% off) — founder-confirmed 2026-04-05
    # Canonical: docs/wiki/MVP-1-Monetizacao-e-Assinaturas.md
    price_cents=22000,
    billing_cycle=BillingCycle.ANNUAL,
    trial_days=7,
    legacy_aliases=("pro_annual",),
)

PUBLIC_BILLING_PLANS: tuple[BillingPlanOffer, ...] = (
    FREE_PLAN,
    PREMIUM_MONTHLY_PLAN,
    PREMIUM_ANNUAL_PLAN,
)


def serialize_billing_plan(offer: BillingPlanOffer) -> BillingPlanPayload:
    return {
        "slug": offer.slug,
        "plan_code": offer.plan_code,
        "tier": offer.tier,
        "billing_cycle": offer.billing_cycle.value if offer.billing_cycle else None,
        "display_name": offer.display_name,
        "description": offer.description,
        "price_cents": offer.price_cents,
        "currency": offer.currency,
        "trial_days": offer.trial_days,
        "checkout_enabled": offer.checkout_enabled,
        "highlighted": offer.highlighted,
    }


def list_public_billing_plans() -> list[BillingPlanPayload]:
    return [serialize_billing_plan(offer) for offer in PUBLIC_BILLING_PLANS]


def resolve_checkout_plan_offer(raw_slug: str | None) -> BillingPlanOffer | None:
    normalized = str(raw_slug or "").strip().lower()
    if not normalized:
        return None

    for offer in PUBLIC_BILLING_PLANS:
        if not offer.checkout_enabled:
            continue
        if normalized == offer.slug:
            return offer
        if normalized in offer.legacy_aliases:
            return offer
    return None


def canonical_offer_slug(
    plan_code: str | None,
    billing_cycle: BillingCycle | None,
) -> str | None:
    normalized_plan = str(plan_code or "").strip().lower()
    if normalized_plan == "free":
        return FREE_PLAN.slug
    if normalized_plan == "trial":
        if billing_cycle == BillingCycle.ANNUAL:
            return PREMIUM_ANNUAL_PLAN.slug
        return PREMIUM_MONTHLY_PLAN.slug
    if normalized_plan == "premium":
        if billing_cycle == BillingCycle.ANNUAL:
            return PREMIUM_ANNUAL_PLAN.slug
        return PREMIUM_MONTHLY_PLAN.slug
    return None


def parse_billing_cycle(raw_value: str | None) -> BillingCycle | None:
    normalized = str(raw_value or "").strip().lower()
    if not normalized:
        return None
    try:
        return BillingCycle(normalized)
    except ValueError:
        return None
