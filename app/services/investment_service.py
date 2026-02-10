from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import requests
from requests.exceptions import RequestException

from config import Config


class InvestmentService:
    _cache: dict[str, tuple[float, Any]] = {}

    @staticmethod
    def _settings() -> tuple[float, int, int]:
        timeout_seconds = float(os.getenv("BRAPI_TIMEOUT_SECONDS", "3"))
        max_retries = int(os.getenv("BRAPI_MAX_RETRIES", "2"))
        cache_ttl_seconds = int(os.getenv("BRAPI_CACHE_TTL_SECONDS", "60"))
        return timeout_seconds, max_retries, cache_ttl_seconds

    @classmethod
    def _cache_get(cls, cache_key: str, ttl_seconds: int) -> Any | None:
        if ttl_seconds <= 0:
            return None
        cache_entry = cls._cache.get(cache_key)
        if not cache_entry:
            return None
        cached_at, payload = cache_entry
        if (time.monotonic() - cached_at) > ttl_seconds:
            cls._cache.pop(cache_key, None)
            return None
        return payload

    @classmethod
    def _cache_set(cls, cache_key: str, payload: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        cls._cache[cache_key] = (time.monotonic(), payload)

    @classmethod
    def _clear_cache_for_tests(cls) -> None:
        cls._cache.clear()

    @staticmethod
    def _request_json(
        endpoint: str, *, params: dict[str, Any] | None = None
    ) -> Any | None:
        timeout_seconds, max_retries, _ = InvestmentService._settings()
        config = Config()
        attempts = max_retries + 1
        for attempt in range(attempts):
            try:
                resp = requests.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {config.BRAPI_KEY}"},
                    params=params,
                    timeout=timeout_seconds,
                )
                resp.raise_for_status()
                return resp.json()
            except RequestException:
                if attempt == attempts - 1:
                    return None
                time.sleep(0.15 * (attempt + 1))
        return None

    @staticmethod
    def get_market_price(ticker: str) -> Optional[float]:
        """Consulta preço de mercado via BRAPI com timeout, retry e cache curto."""
        normalized_ticker = ticker.upper()
        _, _, cache_ttl_seconds = InvestmentService._settings()

        cached_price = InvestmentService._cache_get(
            normalized_ticker, cache_ttl_seconds
        )
        if cached_price is not None:
            return float(cached_price)

        payload = InvestmentService._request_json(
            f"https://brapi.dev/api/quote/{normalized_ticker}"
        )
        if not payload:
            return None
        results = payload.get("results") if isinstance(payload, dict) else None
        if not results:
            return None
        price = float(results[0].get("regularMarketPrice", 0))
        InvestmentService._cache_set(normalized_ticker, price, cache_ttl_seconds)
        return price

    @staticmethod
    def get_historical_prices(
        ticker: str, *, start_date: str, end_date: str
    ) -> dict[str, float]:
        normalized_ticker = ticker.upper()
        _, _, cache_ttl_seconds = InvestmentService._settings()
        cache_key = f"HIST:{normalized_ticker}:{start_date}:{end_date}"
        cached = InvestmentService._cache_get(cache_key, cache_ttl_seconds)
        if cached is not None:
            return dict(cached)

        payload = InvestmentService._request_json(
            f"https://brapi.dev/api/quote/{normalized_ticker}",
            params={
                "range": "5y",
                "interval": "1d",
            },
        )
        if not isinstance(payload, dict):
            return {}
        results = payload.get("results")
        if not results:
            return {}

        historical_rows = results[0].get("historicalDataPrice") or []
        prices: dict[str, float] = {}
        for row in historical_rows:
            if not isinstance(row, dict):
                continue
            unix_ts = row.get("date")
            if not isinstance(unix_ts, (int, float)):
                continue
            close_price = row.get("close")
            if close_price is None:
                continue
            day = datetime.fromtimestamp(float(unix_ts), tz=UTC).date().isoformat()
            if day < start_date or day > end_date:
                continue
            prices[day] = float(close_price)

        InvestmentService._cache_set(cache_key, prices, cache_ttl_seconds)
        return prices

    @staticmethod
    def calculate_estimated_value(data: Dict[str, Any]) -> Optional[float]:
        """
        Dado o payload validado, retorna o valor estimado:
        - Se tiver ticker e quantity, busca preço via get_market_price
        - Se não tiver ticker, usa value * quantity
        """
        ticker = data.get("ticker")
        quantity = data.get("quantity")
        value = data.get("value")

        if ticker and quantity is not None:
            price = InvestmentService.get_market_price(ticker)
            if price is None:
                return None
            return price * float(quantity)
        if value is not None and quantity is not None:
            return float(value) * float(quantity)
        return None
