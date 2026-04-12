"""Tests for PERF-3 slow query log (``app/extensions/slow_query_log.py``)."""

from __future__ import annotations

import logging
import time
from typing import Any
from unittest.mock import patch

import pytest
from flask import Flask
from sqlalchemy import create_engine, text

from app.extensions import slow_query_log as slow_query_log_module
from app.extensions.integration_metrics import (
    reset_metrics_for_tests,
    snapshot_metric_samples,
    snapshot_metrics,
)
from app.extensions.slow_query_log import (
    DEFAULT_THRESHOLD_MS,
    _as_bool,
    _as_int,
    _resolve_config,
    _truncate,
    install_slow_query_log,
)


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset_metrics_for_tests()


def _make_app(**config_overrides: Any) -> Flask:
    app = Flask(__name__)
    app.config.update(config_overrides)
    return app


def _make_engine() -> Any:
    return create_engine("sqlite+pysqlite:///:memory:")


class TestHelpers:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (True, True),
            (False, False),
            ("1", True),
            ("true", True),
            ("YES", True),
            ("on", True),
            ("0", False),
            ("false", False),
            ("no", False),
            ("", False),
        ],
    )
    def test_as_bool(self, value: Any, expected: bool) -> None:
        assert _as_bool(value, default=False) is expected

    def test_as_bool_returns_default_when_none(self) -> None:
        assert _as_bool(None, default=True) is True
        assert _as_bool(None, default=False) is False

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("250", 250),
            (250, 250),
            ("0", 0),
            ("-5", DEFAULT_THRESHOLD_MS),
            ("garbage", DEFAULT_THRESHOLD_MS),
            (None, DEFAULT_THRESHOLD_MS),
        ],
    )
    def test_as_int(self, value: Any, expected: int) -> None:
        assert _as_int(value, default=DEFAULT_THRESHOLD_MS) == expected

    def test_truncate_preserves_short_statements(self) -> None:
        assert _truncate("SELECT 1") == "SELECT 1"

    def test_truncate_collapses_whitespace(self) -> None:
        assert _truncate("SELECT\n   1\n\t FROM t") == "SELECT 1 FROM t"

    def test_truncate_trims_long_statements(self) -> None:
        statement = "SELECT " + "a" * 1000
        truncated = _truncate(statement, limit=50)
        assert len(truncated) == 50
        assert truncated.endswith("…")


class TestResolveConfig:
    def test_uses_defaults_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLOW_QUERY_LOG_ENABLED", raising=False)
        monkeypatch.delenv("SLOW_QUERY_LOG_THRESHOLD_MS", raising=False)
        app = _make_app()
        enabled, threshold = _resolve_config(app)
        assert enabled is True
        assert threshold == DEFAULT_THRESHOLD_MS

    def test_disabled_via_flask_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLOW_QUERY_LOG_ENABLED", raising=False)
        app = _make_app(SLOW_QUERY_LOG_ENABLED=False)
        enabled, _ = _resolve_config(app)
        assert enabled is False

    def test_threshold_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLOW_QUERY_LOG_THRESHOLD_MS", "42")
        app = _make_app()
        _, threshold = _resolve_config(app)
        assert threshold == 42

    def test_flask_config_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLOW_QUERY_LOG_THRESHOLD_MS", "42")
        app = _make_app(SLOW_QUERY_LOG_THRESHOLD_MS=1500)
        _, threshold = _resolve_config(app)
        assert threshold == 1500


class TestInstall:
    def test_skips_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLOW_QUERY_LOG_ENABLED", raising=False)
        app = _make_app(SLOW_QUERY_LOG_ENABLED=False)
        engine = _make_engine()
        assert install_slow_query_log(app, engines=[engine]) is False
        assert getattr(engine, "_auraxis_slow_query_log_installed", False) is False

    def test_install_is_idempotent(self) -> None:
        app = _make_app()
        engine = _make_engine()
        first = install_slow_query_log(app, engines=[engine])
        second = install_slow_query_log(app, engines=[engine])
        assert first is True
        assert second is False
        assert engine._auraxis_slow_query_log_installed is True

    def test_fast_queries_are_not_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _make_app(SLOW_QUERY_LOG_THRESHOLD_MS=500)
        engine = _make_engine()
        install_slow_query_log(app, engines=[engine])

        caplog.set_level(logging.WARNING, logger="auraxis.slow_query")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        assert caplog.records == []
        assert snapshot_metrics(prefix="db.slow_query.") == {}

    def test_slow_query_is_logged_and_recorded(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _make_app(SLOW_QUERY_LOG_THRESHOLD_MS=100)
        engine = _make_engine()
        install_slow_query_log(app, engines=[engine])

        real_perf_counter = time.perf_counter
        fake_clock = iter([10.0, 10.3])  # 300ms delta

        def fake_perf_counter() -> float:
            try:
                return next(fake_clock)
            except StopIteration:
                return real_perf_counter()

        caplog.set_level(logging.WARNING, logger="auraxis.slow_query")
        with patch.object(
            slow_query_log_module.time, "perf_counter", side_effect=fake_perf_counter
        ):
            with engine.connect() as conn:
                conn.execute(text("SELECT 2"))

        slow_warnings = [
            record
            for record in caplog.records
            if record.name == "auraxis.slow_query" and record.levelname == "WARNING"
        ]
        assert len(slow_warnings) == 1
        record = slow_warnings[0]
        assert record.msg == "slow query detected"
        assert record.duration_ms == 300
        assert record.threshold_ms == 100
        assert "SELECT 2" in record.statement

        counters = snapshot_metrics(prefix="db.slow_query.")
        assert counters.get("db.slow_query.total") == 1
        samples = snapshot_metric_samples(prefix="db.slow_query.")
        assert samples.get("db.slow_query.duration_ms") == [300]
