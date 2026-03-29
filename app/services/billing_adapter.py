"""Billing provider adapter — J9 (billing / plan management).

Defines the BillingProvider protocol (structural typing) and a StubBillingProvider
that returns predictable responses for development and testing. Real provider
implementations (e.g. Asaas, Stripe) should implement BillingProvider and be
wired in via dependency injection or a factory.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BillingProvider(Protocol):
    """Structural interface for billing provider adapters."""

    def get_subscription(self, provider_id: str) -> dict[str, Any]:
        """Fetch current subscription state from the provider.

        Returns a dict with at least a ``status`` key.
        """
        ...

    def cancel_subscription(self, provider_id: str) -> dict[str, Any]:
        """Request immediate cancellation of the subscription.

        Returns a dict with at least a ``status`` key.
        """
        ...

    def create_checkout_session(self, user_id: str, plan_slug: str) -> dict[str, Any]:
        """Create a hosted checkout session for the given plan.

        Returns a dict with at least a ``checkout_url`` key.
        """
        ...


class StubBillingProvider:
    """Stub implementation for development and testing.

    Returns predictable, deterministic responses without making any external
    network calls.  Safe to use in CI and unit-test environments.
    """

    _STUB_PROVIDER = "stub"

    def get_subscription(self, provider_id: str) -> dict[str, Any]:
        return {
            "provider_id": provider_id,
            "status": "active",
            "plan_code": "premium",
            "offer_code": "premium_monthly",
            "billing_cycle": "monthly",
            "current_period_start": None,
            "current_period_end": None,
            "provider": self._STUB_PROVIDER,
        }

    def cancel_subscription(self, provider_id: str) -> dict[str, Any]:
        return {
            "provider_id": provider_id,
            "status": "canceled",
            "provider": self._STUB_PROVIDER,
        }

    def create_checkout_session(self, user_id: str, plan_slug: str) -> dict[str, Any]:
        return {
            "checkout_url": f"https://stub.billing/checkout/{plan_slug}?user={user_id}",
            "provider": self._STUB_PROVIDER,
        }


def get_default_billing_provider() -> BillingProvider:
    """Factory that returns the active billing provider.

    Swap this for a real provider implementation when integrating with a payment
    gateway (e.g. Asaas, Stripe).
    """
    return StubBillingProvider()
