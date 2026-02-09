from typing import Any

import requests

from app.services.investment_service import InvestmentService


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], should_raise: bool = False) -> None:
        self._payload = payload
        self._should_raise = should_raise

    def raise_for_status(self) -> None:
        if self._should_raise:
            raise requests.exceptions.HTTPError("boom")

    def json(self) -> dict[str, Any]:
        return self._payload


def test_get_market_price_success(monkeypatch) -> None:
    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"results": [{"regularMarketPrice": 42.5}]})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("petr4") == 42.5


def test_get_market_price_no_results(monkeypatch) -> None:
    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"results": []})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("petr4") is None


def test_get_market_price_request_exception(monkeypatch) -> None:
    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        raise requests.exceptions.RequestException("network error")

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("petr4") is None


def test_calculate_estimated_value_with_ticker(monkeypatch) -> None:
    monkeypatch.setattr(InvestmentService, "get_market_price", lambda ticker: 10.0)
    payload = {"ticker": "vale3", "quantity": 3}

    assert InvestmentService.calculate_estimated_value(payload) == 30.0


def test_calculate_estimated_value_with_ticker_and_missing_price(monkeypatch) -> None:
    monkeypatch.setattr(InvestmentService, "get_market_price", lambda ticker: None)
    payload = {"ticker": "vale3", "quantity": 3}

    assert InvestmentService.calculate_estimated_value(payload) is None


def test_calculate_estimated_value_with_value_and_quantity() -> None:
    payload = {"value": "150.0", "quantity": 2}

    assert InvestmentService.calculate_estimated_value(payload) == 300.0


def test_calculate_estimated_value_missing_required_fields() -> None:
    payload = {"name": "Reserva"}

    assert InvestmentService.calculate_estimated_value(payload) is None
