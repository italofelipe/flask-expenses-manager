"""MarketRatesProvider — Ports & Adapters port for external macro rates.

Used by AI insights to compare a user's portfolio return against benchmark
rates (CDI, IPCA) without hard-coding HTTP calls inside business logic.

Concrete implementations
------------------------
``BcbMarketRatesProvider`` — adapter for BCB SGS series via the public API
    ``https://api.bcb.gov.br/dados/serie/bcdata.sgs.<id>/dados``. Cached
    through ``cache_service`` for 24h (rates are end-of-day).

``StubMarketRatesProvider`` — deterministic provider for tests; values
    overridable via environment variables.

Failure model
-------------
Network errors, malformed payloads and unknown series all degrade to
``None`` and a structured warning. Callers MUST handle ``None`` by omitting
the comparison and flagging ``data_quality.missing_external_rates``.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

# Banco Central do Brasil — SGS series ids.
#   4391 — CDI monthly return (% a.m.)
#   433  — IPCA monthly variation (% a.m.)
_SGS_CDI_MONTHLY = 4391
_SGS_IPCA_MONTHLY = 433
_BCB_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series}/dados"
_HTTP_TIMEOUT_SECONDS = 5.0
_CACHE_TTL_SECONDS = 24 * 60 * 60


@runtime_checkable
class MarketRatesProvider(Protocol):
    """Port every macro-rate adapter must satisfy."""

    def cdi_monthly(self, *, year: int, month: int) -> Decimal | None:
        """Return CDI accumulated for the given month as a Decimal % (e.g. 0.92)."""
        ...

    def ipca_monthly(self, *, year: int, month: int) -> Decimal | None:
        """Return IPCA monthly variation as a Decimal % (e.g. 0.45)."""
        ...


def _cache_key(series_id: int, year: int, month: int) -> str:
    return f"bcb:sgs:{series_id}:{year:04d}-{month:02d}"


class BcbMarketRatesProvider:
    """BCB SGS adapter. Network-friendly with graceful failure."""

    def cdi_monthly(self, *, year: int, month: int) -> Decimal | None:
        return _fetch_sgs_series_value(_SGS_CDI_MONTHLY, year=year, month=month)

    def ipca_monthly(self, *, year: int, month: int) -> Decimal | None:
        return _fetch_sgs_series_value(_SGS_IPCA_MONTHLY, year=year, month=month)


class StubMarketRatesProvider:
    """Test provider — returns configured values via env or constructor."""

    def __init__(
        self,
        *,
        cdi: Decimal | None = None,
        ipca: Decimal | None = None,
    ) -> None:
        self._cdi = cdi
        self._ipca = ipca

    def cdi_monthly(self, *, year: int, month: int) -> Decimal | None:  # noqa: ARG002
        if self._cdi is not None:
            return self._cdi
        raw = os.getenv("AI_MARKET_RATE_CDI_MONTHLY")
        return _decimal_or_none(raw)

    def ipca_monthly(self, *, year: int, month: int) -> Decimal | None:  # noqa: ARG002
        if self._ipca is not None:
            return self._ipca
        raw = os.getenv("AI_MARKET_RATE_IPCA_MONTHLY")
        return _decimal_or_none(raw)


def _decimal_or_none(raw: str | None) -> Decimal | None:
    if raw is None or not raw.strip():
        return None
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError):
        return None


def _fetch_sgs_series_value(
    series_id: int,
    *,
    year: int,
    month: int,
) -> Decimal | None:
    """Fetch a single month's value from BCB SGS, with cache + graceful failure."""
    cache_key = _cache_key(series_id, year, month)
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    target = date(year, month, 1)
    last_day = _last_day_of_month(year, month)
    params = {
        "formato": "json",
        "dataInicial": target.strftime("%d/%m/%Y"),
        "dataFinal": last_day.strftime("%d/%m/%Y"),
    }
    url = _BCB_BASE.format(series=series_id) + "?" + urlencode(params)
    request = Request(  # noqa: S310 — fixed-host BCB public API
        url,
        headers={"Accept": "application/json", "User-Agent": "auraxis-ai-insights"},
    )

    try:
        with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        log.warning(
            "ai_advisory.market_rates.fetch_failed series=%s ym=%04d-%02d error=%s",
            series_id,
            year,
            month,
            exc,
        )
        return None

    value = _parse_sgs_payload(payload, target_year=year, target_month=month)
    if value is not None:
        _set_cached(cache_key, value)
    return value


def _parse_sgs_payload(
    payload: object,
    *,
    target_year: int,
    target_month: int,
) -> Decimal | None:
    if not isinstance(payload, list):
        return None
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        date_str = entry.get("data")
        value_str = entry.get("valor")
        if not (isinstance(date_str, str) and isinstance(value_str, str)):
            continue
        try:
            parsed = datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            continue
        if parsed.year == target_year and parsed.month == target_month:
            return _decimal_or_none(value_str.replace(",", "."))
    return None


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return date.fromordinal(next_month.toordinal() - 1)


def _get_cached(key: str) -> Decimal | None:
    try:
        from app.services.cache_service import get_cache_service

        raw = get_cache_service().get(key)
    except Exception:  # pragma: no cover — cache outage stays silent
        return None
    if raw is None:
        return None
    if isinstance(raw, (int, float, str)):
        return _decimal_or_none(str(raw))
    return None


def _set_cached(key: str, value: Decimal) -> None:
    try:
        from app.services.cache_service import get_cache_service

        get_cache_service().set(key, str(value), ttl=_CACHE_TTL_SECONDS)
    except Exception:  # pragma: no cover
        pass


# ── Singleton factory ─────────────────────────────────────────────────────────

_default_provider: MarketRatesProvider | None = None


def get_default_market_rates_provider() -> MarketRatesProvider:
    """Return the process-level market rates provider (lazy singleton).

    Tests should call ``reset_market_rates_provider_for_tests()`` and
    inject a ``StubMarketRatesProvider`` via the explicit ``market_rates``
    argument on AIAdvisoryService when needed.
    """
    global _default_provider  # noqa: PLW0603
    if _default_provider is None:
        if os.getenv("AI_MARKET_RATES_PROVIDER", "bcb").lower() == "stub":
            _default_provider = StubMarketRatesProvider()
        else:
            _default_provider = BcbMarketRatesProvider()
    return _default_provider


def reset_market_rates_provider_for_tests() -> None:
    """Reset the singleton so tests can inject a custom provider."""
    global _default_provider  # noqa: PLW0603
    _default_provider = None


__all__ = [
    "BcbMarketRatesProvider",
    "MarketRatesProvider",
    "StubMarketRatesProvider",
    "get_default_market_rates_provider",
    "reset_market_rates_provider_for_tests",
]
