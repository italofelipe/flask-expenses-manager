from __future__ import annotations

from typing import Any

import pytest
import requests

from app.extensions.integration_metrics import build_brapi_metrics_payload
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


def test_brapi_timeout_metric_increments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAPI_MAX_RETRIES", "0")

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        raise requests.exceptions.Timeout("timeout")

    monkeypatch.setattr(requests, "get", _fake_get)

    payload = InvestmentService._request_json("https://brapi.dev/api/quote/PETR4")
    assert payload is None
    metrics = build_brapi_metrics_payload()
    assert metrics["summary"]["timeouts"] == 1


def test_brapi_http_error_metric_increments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAPI_MAX_RETRIES", "0")

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({}, should_raise=True)

    monkeypatch.setattr(requests, "get", _fake_get)

    payload = InvestmentService._request_json("https://brapi.dev/api/quote/VALE3")
    assert payload is None
    metrics = build_brapi_metrics_payload()
    assert metrics["summary"]["http_errors"] == 1


def test_brapi_invalid_payload_metric_increments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAPI_MAX_RETRIES", "0")

    def _fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"results": [{"regularMarketPrice": "invalid"}]})

    monkeypatch.setattr(requests, "get", _fake_get)

    price = InvestmentService.get_market_price("PETR4")
    assert price is None
    metrics = build_brapi_metrics_payload()
    assert metrics["summary"]["invalid_payloads"] >= 1
