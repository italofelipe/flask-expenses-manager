"""Canonical Prometheus metrics for auraxis-api (API23).

Exposes three core instrument families via ``prometheus_client``:

- ``auraxis_http_requests_total``           — Counter {method, endpoint, status_code}
- ``auraxis_http_request_duration_seconds`` — Histogram {method, endpoint}
- ``auraxis_auth_logins_total``             — Counter {status}

All metrics are process-level singletons.  They are safe under gunicorn
multi-worker fork mode because each worker gets its own copy after forking.
For spawn-mode multiprocess, set ``PROMETHEUS_MULTIPROC_DIR`` — the
prometheus_client library will aggregate across workers automatically.

Usage
-----
Call ``register_prometheus_middleware(app)`` once in ``create_app()`` to wire
the request instrumentation hooks.  The ``/ops/metrics`` endpoint is handled
by the observability controller which calls ``generate_latest_metrics()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False

_HTTP_REQUESTS_TOTAL: Any = None
_HTTP_REQUEST_DURATION: Any = None
_AUTH_LOGINS_TOTAL: Any = None
_AUDIT_EVENTS_PURGED_TOTAL: Any = None

_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


def _ensure_metrics_initialized() -> None:
    """Lazily initialise Prometheus metric objects (idempotent)."""
    global \
        _HTTP_REQUESTS_TOTAL, \
        _HTTP_REQUEST_DURATION, \
        _AUTH_LOGINS_TOTAL, \
        _AUDIT_EVENTS_PURGED_TOTAL

    if not _PROMETHEUS_AVAILABLE:
        return

    if _HTTP_REQUESTS_TOTAL is None:
        _HTTP_REQUESTS_TOTAL = Counter(
            "auraxis_http_requests_total",
            "Total HTTP requests handled by auraxis-api",
            ["method", "endpoint", "status_code"],
        )

    if _HTTP_REQUEST_DURATION is None:
        _HTTP_REQUEST_DURATION = Histogram(
            "auraxis_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=_DURATION_BUCKETS,
        )

    if _AUTH_LOGINS_TOTAL is None:
        _AUTH_LOGINS_TOTAL = Counter(
            "auraxis_auth_logins_total",
            "Total login attempts (status: success | failure | mfa_required)",
            ["status"],
        )

    if _AUDIT_EVENTS_PURGED_TOTAL is None:
        _AUDIT_EVENTS_PURGED_TOTAL = Counter(
            "auraxis_audit_events_purged_total",
            "Total audit_events rows deleted by the retention job",
        )


def record_http_request(
    *,
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Increment request counter and observe duration histogram."""
    _ensure_metrics_initialized()
    if _HTTP_REQUESTS_TOTAL is not None:
        _HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
        ).inc()
    if _HTTP_REQUEST_DURATION is not None:
        _HTTP_REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration_seconds)


def record_audit_purge(count: int) -> None:
    """Increment ``auraxis_audit_events_purged_total`` by *count* rows deleted."""
    _ensure_metrics_initialized()
    if _AUDIT_EVENTS_PURGED_TOTAL is not None:
        _AUDIT_EVENTS_PURGED_TOTAL.inc(count)


def record_auth_login(*, status: str) -> None:
    """Increment ``auraxis_auth_logins_total`` with the given status label.

    Canonical status values: ``success``, ``failure``, ``mfa_required``.
    """
    _ensure_metrics_initialized()
    if _AUTH_LOGINS_TOTAL is not None:
        _AUTH_LOGINS_TOTAL.labels(status=status).inc()


def generate_latest_metrics() -> tuple[bytes, str]:
    """Return ``(body_bytes, content_type)`` for the Prometheus scrape endpoint.

    Falls back to an empty payload when ``prometheus_client`` is not installed.
    """
    _ensure_metrics_initialized()
    if not _PROMETHEUS_AVAILABLE:
        return b"", "text/plain; version=0.0.4; charset=utf-8"  # pragma: no cover
    body: bytes = generate_latest()
    content_type: str = CONTENT_TYPE_LATEST
    return body, content_type


def register_prometheus_middleware(app: "Flask") -> None:
    """Wire before/after_request hooks to populate Prometheus metrics."""
    from time import perf_counter

    from flask import Response, g

    _ensure_metrics_initialized()

    @app.before_request
    def _prom_mark_start() -> None:
        g.prom_request_started_at = perf_counter()

    @app.after_request
    def _prom_record_request(response: Response) -> Response:
        from app.http.request_context import get_request_context

        started_at: float | None = getattr(g, "prom_request_started_at", None)
        duration = (
            max(perf_counter() - started_at, 0.0)
            if isinstance(started_at, float)
            else 0.0
        )
        ctx = get_request_context(optional=True)
        method = ctx.method if ctx else "UNKNOWN"
        endpoint = (ctx.endpoint or ctx.path) if ctx else "unknown"
        record_http_request(
            method=method,
            endpoint=endpoint,
            status_code=response.status_code,
            duration_seconds=duration,
        )
        return response


__all__ = [
    "generate_latest_metrics",
    "record_audit_purge",
    "record_auth_login",
    "record_http_request",
    "register_prometheus_middleware",
]
