from typing import Any

import pytest
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


def test_get_market_price_success(monkeypatch: pytest.MonkeyPatch) -> None:
    InvestmentService._clear_cache_for_tests()

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"results": [{"regularMarketPrice": 42.5}]})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("petr4") == 42.5


def test_get_market_price_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    InvestmentService._clear_cache_for_tests()

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"results": []})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("petr4") is None


def test_get_market_price_request_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    InvestmentService._clear_cache_for_tests()

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        raise requests.exceptions.RequestException("network error")

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("petr4") is None


def test_get_market_price_rejects_invalid_ticker_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()

    called = {"value": False}

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        called["value"] = True
        return _FakeResponse({"results": [{"regularMarketPrice": 42.5}]})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("PETR4<script>") is None
    assert called["value"] is False


def test_get_market_price_rejects_invalid_provider_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"results": [{"regularMarketPrice": "invalid"}]})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("petr4") is None


def test_get_market_price_retries_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()
    monkeypatch.setenv("BRAPI_MAX_RETRIES", "2")
    monkeypatch.setenv("BRAPI_CACHE_TTL_SECONDS", "0")

    calls = {"count": 0}

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.exceptions.Timeout("timeout")
        return _FakeResponse({"results": [{"regularMarketPrice": 30.0}]})

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr("app.services.investment_service.time.sleep", lambda _: None)

    assert InvestmentService.get_market_price("vale3") == 30.0
    assert calls["count"] == 2


def test_get_market_price_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()
    monkeypatch.setenv("BRAPI_TIMEOUT_SECONDS", "4")
    monkeypatch.setenv("BRAPI_CACHE_TTL_SECONDS", "0")

    captured: dict[str, Any] = {}

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        captured.update(kwargs)
        return _FakeResponse({"results": [{"regularMarketPrice": 12.5}]})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("itub4") == 12.5
    assert captured["timeout"] == 4.0


def test_get_market_price_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    InvestmentService._clear_cache_for_tests()
    monkeypatch.setenv("BRAPI_CACHE_TTL_SECONDS", "60")

    calls = {"count": 0}

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        calls["count"] += 1
        return _FakeResponse({"results": [{"regularMarketPrice": 18.0}]})

    monkeypatch.setattr(requests, "get", _fake_get)

    assert InvestmentService.get_market_price("bbas3") == 18.0
    assert InvestmentService.get_market_price("bbas3") == 18.0
    assert calls["count"] == 1


def test_get_historical_prices_success_and_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()
    monkeypatch.setenv("BRAPI_CACHE_TTL_SECONDS", "60")

    calls = {"count": 0}

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        calls["count"] += 1
        return _FakeResponse(
            {
                "results": [
                    {
                        "historicalDataPrice": [
                            {"date": 1739059200, "close": 21.5},  # 2025-02-09
                            {"date": 1739145600, "close": 22.0},  # 2025-02-10
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr(requests, "get", _fake_get)

    prices = InvestmentService.get_historical_prices(
        "petr4", start_date="2025-02-09", end_date="2025-02-10"
    )
    assert prices["2025-02-09"] == 21.5
    assert prices["2025-02-10"] == 22.0
    # Segunda chamada deve vir do cache.
    prices_cached = InvestmentService.get_historical_prices(
        "petr4", start_date="2025-02-09", end_date="2025-02-10"
    )
    assert prices_cached == prices
    assert calls["count"] == 1


def test_get_historical_prices_request_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        raise requests.exceptions.RequestException("network error")

    monkeypatch.setattr(requests, "get", _fake_get)
    prices = InvestmentService.get_historical_prices(
        "vale3", start_date="2025-02-09", end_date="2025-02-10"
    )
    assert prices == {}


def test_get_historical_prices_rejects_invalid_ticker_format() -> None:
    prices = InvestmentService.get_historical_prices(
        "BAD<script>", start_date="2025-02-09", end_date="2025-02-10"
    )
    assert prices == {}


def test_internal_helpers_handle_defensive_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # _normalize_ticker -> empty after trim
    assert InvestmentService._normalize_ticker("   ") is None

    # _extract_market_price -> first result must be dict
    assert InvestmentService._extract_market_price({"results": ["invalid"]}) is None
    # _extract_market_price -> price must be positive number
    assert (
        InvestmentService._extract_market_price(
            {"results": [{"regularMarketPrice": 0}]}
        )
        is None
    )

    # _request_json -> for loop not entered when attempts == 0
    monkeypatch.setenv("BRAPI_MAX_RETRIES", "-1")
    assert InvestmentService._request_json("https://example.com") is None


def test_cache_get_expires_entry() -> None:
    InvestmentService._clear_cache_for_tests()
    InvestmentService._cache["CACHE:KEY"] = (0.0, {"value": 1})

    # Simula tempo atual além do TTL para forçar expiração e remoção da chave.
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.services.investment_service.time.monotonic", lambda: 10.0
        )
        assert InvestmentService._cache_get("CACHE:KEY", ttl_seconds=1) is None

    assert "CACHE:KEY" not in InvestmentService._cache


def test_get_historical_prices_skips_invalid_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()
    monkeypatch.setenv("BRAPI_CACHE_TTL_SECONDS", "0")

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(
            {
                "results": [
                    {
                        "historicalDataPrice": [
                            "invalid-row",
                            {"date": "bad", "close": 10},
                            {"date": 1739059200, "close": "bad"},
                            {"date": 1738886400, "close": 12.0},  # fora do range
                            {"date": 1739145600, "close": 22.0},  # válido
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr(requests, "get", _fake_get)
    prices = InvestmentService.get_historical_prices(
        "petr4", start_date="2025-02-09", end_date="2025-02-10"
    )
    assert prices == {"2025-02-10": 22.0}


def test_get_historical_prices_requires_results_as_dict_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    InvestmentService._clear_cache_for_tests()

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"results": ["invalid"]})

    monkeypatch.setattr(requests, "get", _fake_get)
    prices = InvestmentService.get_historical_prices(
        "petr4", start_date="2025-02-09", end_date="2025-02-10"
    )
    assert prices == {}


def test_calculate_estimated_value_with_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(InvestmentService, "get_market_price", lambda ticker: 10.0)
    payload = {"ticker": "vale3", "quantity": 3}

    assert InvestmentService.calculate_estimated_value(payload) == 30.0


def test_calculate_estimated_value_with_ticker_and_missing_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(InvestmentService, "get_market_price", lambda ticker: None)
    payload = {"ticker": "vale3", "quantity": 3}

    assert InvestmentService.calculate_estimated_value(payload) is None


def test_calculate_estimated_value_with_value_and_quantity() -> None:
    payload = {"value": "150.0", "quantity": 2}

    assert InvestmentService.calculate_estimated_value(payload) == 300.0


def test_calculate_estimated_value_missing_required_fields() -> None:
    payload = {"name": "Reserva"}

    assert InvestmentService.calculate_estimated_value(payload) is None
