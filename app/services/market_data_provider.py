"""MarketDataProvider — Ports & Adapters port for stock market data (ARC-API-01).

The ``MarketDataProvider`` Protocol is the formal *port* that decouples
business logic from the BRAPI HTTP adapter.  Any class that implements the
three required methods is structurally compatible, enabling easy substitution
for testing (mock providers) or migration to alternative data providers.

Concrete implementations
------------------------
``BrapiMarketDataProvider``  — delegates to the existing ``InvestmentService``
    static class, which already handles circuit-breaking, caching, and retry.

Factory
-------
``get_default_market_data_provider()`` returns the process-level singleton.
``reset_market_data_provider_for_tests()`` resets the singleton between tests.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class MarketDataProvider(Protocol):
    """Port that every market-data adapter must satisfy."""

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Return the current market price for *ticker*, or ``None`` on failure."""
        ...

    def get_historical_prices(
        self,
        ticker: str,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, float]:
        """Return a ``{YYYY-MM-DD: price}`` map for the requested date range."""
        ...

    def calculate_estimated_value(self, data: dict[str, Any]) -> Optional[float]:
        """Return the estimated portfolio value for an investment payload dict."""
        ...


class BrapiMarketDataProvider:
    """Adapter that wraps ``InvestmentService`` as a ``MarketDataProvider`` instance.

    ``InvestmentService`` is a static utility class.  This thin wrapper makes
    it injectable via the protocol without changing any existing call sites.
    """

    def get_current_price(self, ticker: str) -> Optional[float]:
        from app.services.investment_service import InvestmentService

        return InvestmentService.get_market_price(ticker)

    def get_historical_prices(
        self,
        ticker: str,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, float]:
        from app.services.investment_service import InvestmentService

        return InvestmentService.get_historical_prices(
            ticker,
            start_date=start_date,
            end_date=end_date,
        )

    def calculate_estimated_value(self, data: dict[str, Any]) -> Optional[float]:
        from app.services.investment_service import InvestmentService

        return InvestmentService.calculate_estimated_value(data)


# ── Singleton factory ─────────────────────────────────────────────────────────

_default_provider: MarketDataProvider | None = None


def get_default_market_data_provider() -> MarketDataProvider:
    """Return the process-level market data provider (lazy singleton)."""
    global _default_provider  # noqa: PLW0603
    if _default_provider is None:
        _default_provider = BrapiMarketDataProvider()
    return _default_provider


def reset_market_data_provider_for_tests() -> None:
    """Reset the singleton so tests can inject a custom provider."""
    global _default_provider  # noqa: PLW0603
    _default_provider = None


__all__ = [
    "BrapiMarketDataProvider",
    "MarketDataProvider",
    "get_default_market_data_provider",
    "reset_market_data_provider_for_tests",
]
