"""Slow query log (PERF-3).

Hooks SQLAlchemy's engine ``before_cursor_execute`` / ``after_cursor_execute``
events to measure every statement and emit a structured warning whenever the
elapsed time crosses a configurable threshold. Threshold and enablement are
driven by Flask config (and by extension, the environment):

- ``SLOW_QUERY_LOG_ENABLED`` (bool, default ``True``) — master switch.
- ``SLOW_QUERY_LOG_THRESHOLD_MS`` (int, default ``500``) — minimum duration
  to log. Anything below stays silent.

The handler is idempotent: installing twice on the same engine is a no-op.
Metrics are incremented via ``integration_metrics`` so dashboards and CI
probes can assert on them without parsing log lines.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterable
from typing import Any

from flask import Flask, has_request_context, request
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.extensions.database import db
from app.extensions.integration_metrics import increment_metric, record_metric_sample

logger = logging.getLogger("auraxis.slow_query")

_QUERY_START_KEY = "auraxis_slow_query_start"
_INSTALLED_FLAG = "_auraxis_slow_query_log_installed"

DEFAULT_THRESHOLD_MS = 500


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _resolve_config(app: Flask) -> tuple[bool, int]:
    enabled = _as_bool(
        app.config.get("SLOW_QUERY_LOG_ENABLED", os.getenv("SLOW_QUERY_LOG_ENABLED")),
        default=True,
    )
    threshold = _as_int(
        app.config.get(
            "SLOW_QUERY_LOG_THRESHOLD_MS",
            os.getenv("SLOW_QUERY_LOG_THRESHOLD_MS"),
        ),
        default=DEFAULT_THRESHOLD_MS,
    )
    return enabled, threshold


def _truncate(statement: str, limit: int = 500) -> str:
    flat = " ".join(statement.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1] + "…"


def _request_context() -> dict[str, str]:
    if not has_request_context():
        return {}
    return {
        "method": request.method,
        "path": request.path,
    }


def _emit(
    *,
    threshold_ms: int,
    duration_ms: int,
    statement: str,
) -> None:
    increment_metric("db.slow_query.total")
    record_metric_sample("db.slow_query.duration_ms", duration_ms)
    logger.warning(
        "slow query detected",
        extra={
            "duration_ms": duration_ms,
            "threshold_ms": threshold_ms,
            "statement": _truncate(statement),
            **_request_context(),
        },
    )


def _make_before_listener() -> Any:
    def _before(
        _conn: Any,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        if context is not None:
            context._query_start_time = time.perf_counter()  # noqa: SLF001
        else:
            _conn.info[_QUERY_START_KEY] = time.perf_counter()

    return _before


def _make_after_listener(threshold_ms: int) -> Any:
    def _after(
        conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        start: float | None = None
        if context is not None:
            start = getattr(context, "_query_start_time", None)
        if start is None:
            start = conn.info.get(_QUERY_START_KEY) if hasattr(conn, "info") else None
        if start is None:
            return
        duration_ms = int((time.perf_counter() - start) * 1000)
        if duration_ms < threshold_ms:
            return
        _emit(
            threshold_ms=threshold_ms,
            duration_ms=duration_ms,
            statement=statement,
        )

    return _after


def _attach_listeners(engine: Engine, threshold_ms: int) -> bool:
    if getattr(engine, _INSTALLED_FLAG, False):
        return False
    event.listen(engine, "before_cursor_execute", _make_before_listener())
    event.listen(engine, "after_cursor_execute", _make_after_listener(threshold_ms))
    engine._auraxis_slow_query_log_installed = True  # type: ignore[attr-defined]
    logger.info("slow query log installed (threshold=%dms)", threshold_ms)
    return True


def install_slow_query_log(
    app: Flask,
    *,
    engines: Iterable[Engine] | None = None,
) -> bool:
    """Install the slow query log listeners.

    Returns ``True`` when at least one engine received new listeners,
    ``False`` when the feature is disabled or the engines were already
    instrumented.
    """

    enabled, threshold_ms = _resolve_config(app)
    if not enabled:
        logger.debug("slow query log disabled via config")
        return False

    if engines is None:
        with app.app_context():
            target_engines: list[Engine] = [db.engine]
    else:
        target_engines = list(engines)

    return any(_attach_listeners(engine, threshold_ms) for engine in target_engines)
