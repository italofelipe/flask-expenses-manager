"""Tests for the MarketDataProvider port and BrapiMarketDataProvider adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.market_data_provider import (
    BrapiMarketDataProvider,
    MarketDataProvider,
    get_default_market_data_provider,
    reset_market_data_provider_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_market_data_provider_for_tests()
    yield
    reset_market_data_provider_for_tests()


class TestMarketDataProviderProtocol:
    def test_brapi_satisfies_protocol(self):
        provider = BrapiMarketDataProvider()
        assert isinstance(provider, MarketDataProvider)

    def test_factory_returns_brapi_by_default(self):
        provider = get_default_market_data_provider()
        assert isinstance(provider, BrapiMarketDataProvider)

    def test_factory_is_singleton(self):
        p1 = get_default_market_data_provider()
        p2 = get_default_market_data_provider()
        assert p1 is p2

    def test_reset_clears_singleton(self):
        p1 = get_default_market_data_provider()
        reset_market_data_provider_for_tests()
        p2 = get_default_market_data_provider()
        assert p1 is not p2


class TestBrapiMarketDataProvider:
    def test_get_current_price_delegates_to_investment_service(self):
        with patch(
            "app.services.investment_service.InvestmentService.get_market_price",
            return_value=42.50,
        ) as mock_fn:
            provider = BrapiMarketDataProvider()
            price = provider.get_current_price("PETR4")
            assert price == 42.50
            mock_fn.assert_called_once_with("PETR4")

    def test_get_current_price_returns_none_on_failure(self):
        with patch(
            "app.services.investment_service.InvestmentService.get_market_price",
            return_value=None,
        ):
            provider = BrapiMarketDataProvider()
            assert provider.get_current_price("INVALID") is None

    def test_get_historical_prices_delegates(self):
        expected = {"2026-01-01": 35.0, "2026-01-02": 36.0}
        with patch(
            "app.services.investment_service.InvestmentService.get_historical_prices",
            return_value=expected,
        ) as mock_fn:
            provider = BrapiMarketDataProvider()
            result = provider.get_historical_prices(
                "PETR4", start_date="2026-01-01", end_date="2026-01-02"
            )
            assert result == expected
            mock_fn.assert_called_once_with(
                "PETR4", start_date="2026-01-01", end_date="2026-01-02"
            )

    def test_calculate_estimated_value_delegates(self):
        with patch(
            "app.services.investment_service.InvestmentService.calculate_estimated_value",
            return_value=850.0,
        ) as mock_fn:
            provider = BrapiMarketDataProvider()
            data = {"ticker": "PETR4", "quantity": 20}
            result = provider.calculate_estimated_value(data)
            assert result == 850.0
            mock_fn.assert_called_once_with(data)

    def test_mock_provider_satisfies_protocol(self):
        mock = MagicMock(spec=BrapiMarketDataProvider)
        assert isinstance(mock, MarketDataProvider)
