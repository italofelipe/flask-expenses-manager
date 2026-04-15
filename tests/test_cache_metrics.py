"""Tests for Prometheus cache metrics (issue #1056).

Covers:
- Cache hit increments auraxis_cache_hits_total{namespace=...}
- Cache miss increments auraxis_cache_misses_total{namespace=...}
- Cache invalidate increments auraxis_cache_invalidations_total{namespace=...}
- invalidate_pattern increments per key deleted
- Namespace is extracted from the key prefix (first segment before ':')
- No-op when prometheus_client is unavailable (graceful degradation)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.extensions.prometheus_metrics import (
    _ensure_metrics_initialized,
    record_cache_hit,
    record_cache_invalidation,
    record_cache_miss,
)
from app.services.cache_service import RedisCacheService, reset_cache_service_for_tests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_service(get_return=None) -> tuple[RedisCacheService, MagicMock]:
    client = MagicMock()
    client.get.return_value = b'{"v": 1}' if get_return is True else None
    svc = RedisCacheService(client)
    return svc, client


# ---------------------------------------------------------------------------
# Unit tests for recording functions
# ---------------------------------------------------------------------------


class TestPrometheusRecordingFunctions:
    def test_record_cache_hit_increments_counter(self, app) -> None:
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_HITS_TOTAL

            if _CACHE_HITS_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            before = _CACHE_HITS_TOTAL.labels(namespace="dashboard")._value.get()
            record_cache_hit("dashboard")
            after = _CACHE_HITS_TOTAL.labels(namespace="dashboard")._value.get()
            assert after == before + 1

    def test_record_cache_miss_increments_counter(self, app) -> None:
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_MISSES_TOTAL

            if _CACHE_MISSES_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            before = _CACHE_MISSES_TOTAL.labels(namespace="brapi")._value.get()
            record_cache_miss("brapi")
            after = _CACHE_MISSES_TOTAL.labels(namespace="brapi")._value.get()
            assert after == before + 1

    def test_record_cache_invalidation_increments_counter(self, app) -> None:
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_INVALIDATIONS_TOTAL

            if _CACHE_INVALIDATIONS_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            before = _CACHE_INVALIDATIONS_TOTAL.labels(
                namespace="entitlement"
            )._value.get()
            record_cache_invalidation("entitlement")
            after = _CACHE_INVALIDATIONS_TOTAL.labels(
                namespace="entitlement"
            )._value.get()
            assert after == before + 1

    def test_record_functions_noop_when_prometheus_unavailable(self) -> None:
        """Graceful degradation — no exception raised when counters are None."""
        import app.extensions.prometheus_metrics as prom

        # Patch both the counters AND the initializer so the registry is not
        # touched (re-registering already-registered metrics raises ValueError).
        noop = lambda: None  # noqa: E731
        with (
            patch.object(prom, "_ensure_metrics_initialized", noop),
            patch.object(prom, "_CACHE_HITS_TOTAL", None),
            patch.object(prom, "_CACHE_MISSES_TOTAL", None),
            patch.object(prom, "_CACHE_INVALIDATIONS_TOTAL", None),
        ):
            # None of these should raise
            record_cache_hit("dashboard")
            record_cache_miss("dashboard")
            record_cache_invalidation("dashboard")


# ---------------------------------------------------------------------------
# Integration: RedisCacheService instrumentation
# ---------------------------------------------------------------------------


class TestRedisCacheServiceMetrics:
    def setup_method(self) -> None:
        reset_cache_service_for_tests()

    def test_get_hit_records_hit(self, app) -> None:
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_HITS_TOTAL

            if _CACHE_HITS_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            svc, _ = _make_redis_service(get_return=True)
            before = _CACHE_HITS_TOTAL.labels(namespace="dashboard")._value.get()
            result = svc.get("dashboard:overview:abc:2026-04")
            assert result is not None
            after = _CACHE_HITS_TOTAL.labels(namespace="dashboard")._value.get()
            assert after == before + 1

    def test_get_miss_records_miss(self, app) -> None:
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_MISSES_TOTAL

            if _CACHE_MISSES_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            svc, _ = _make_redis_service(get_return=False)
            before = _CACHE_MISSES_TOTAL.labels(namespace="portfolio")._value.get()
            result = svc.get("portfolio:valuation:abc")
            assert result is None
            after = _CACHE_MISSES_TOTAL.labels(namespace="portfolio")._value.get()
            assert after == before + 1

    def test_invalidate_records_invalidation(self, app) -> None:
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_INVALIDATIONS_TOTAL

            if _CACHE_INVALIDATIONS_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            svc, _ = _make_redis_service()
            before = _CACHE_INVALIDATIONS_TOTAL.labels(
                namespace="dashboard"
            )._value.get()
            svc.invalidate("dashboard:overview:abc:2026-04")
            after = _CACHE_INVALIDATIONS_TOTAL.labels(
                namespace="dashboard"
            )._value.get()
            assert after == before + 1

    def test_invalidate_pattern_records_per_key(self, app) -> None:
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_INVALIDATIONS_TOTAL

            if _CACHE_INVALIDATIONS_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            client = MagicMock()
            # SCAN returns (cursor=0, [key1, key2]) — single page
            client.scan.return_value = (0, [b"dashboard:x", b"dashboard:y"])
            svc = RedisCacheService(client)

            before = _CACHE_INVALIDATIONS_TOTAL.labels(
                namespace="dashboard"
            )._value.get()
            svc.invalidate_pattern("dashboard:*")
            after = _CACHE_INVALIDATIONS_TOTAL.labels(
                namespace="dashboard"
            )._value.get()
            assert after == before + 2

    def test_namespace_extracted_from_key_prefix(self, app) -> None:
        """Namespace is always the first colon-delimited segment."""
        with app.app_context():
            _ensure_metrics_initialized()
            from app.extensions.prometheus_metrics import _CACHE_MISSES_TOTAL

            if _CACHE_MISSES_TOTAL is None:
                pytest.skip("prometheus_client not installed")

            svc, _ = _make_redis_service(get_return=False)
            before = _CACHE_MISSES_TOTAL.labels(namespace="brapi")._value.get()
            svc.get("brapi:quote:PETR4")
            after = _CACHE_MISSES_TOTAL.labels(namespace="brapi")._value.get()
            assert after == before + 1
