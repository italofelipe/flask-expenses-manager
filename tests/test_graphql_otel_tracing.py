"""Tests for OpenTelemetry tracing integration in GraphQL resolvers.

The suite uses the OTel SDK's InMemorySpanExporter with AlwaysOnSampler so
that spans are always captured regardless of the configured sampling rate.
Tests verify that:

- ``log_graphql_resolver`` emits a child span with the correct attributes.
- The span is recorded on both success and exception paths.
- Span attributes include graphql.operation_name, auraxis.user_id_hash,
  graphql.duration_ms.
- Exception spans call span.record_exception (status ERROR).
- The no-op path (tracer not configured) never raises.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from app.graphql.observability import log_graphql_resolver

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def span_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture()
def tracer(span_exporter: InMemorySpanExporter):  # type: ignore[no-untyped-def]
    """Return an OTel tracer backed by InMemorySpanExporter + AlwaysOnSampler."""
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider.get_tracer("test")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_resolver(operation_name: str, *, raises: Exception | None = None):
    """Build a wrapped resolver using the decorator under test."""

    @log_graphql_resolver(operation_name)
    def mutate(self, info, **kwargs):  # type: ignore[no-untyped-def]
        if raises:
            raise raises
        return f"ok:{operation_name}"

    return mutate


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestSpanOnSuccess:
    def test_span_name_matches_operation(
        self, tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        mutate = _make_resolver("createGoal")
        with patch("app.extensions.otel.get_tracer", return_value=tracer):
            result = mutate(None, None)

        assert result == "ok:createGoal"
        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "graphql.resolver.createGoal"

    def test_span_has_operation_name_attribute(
        self, tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        mutate = _make_resolver("updateTransaction")
        with patch("app.extensions.otel.get_tracer", return_value=tracer):
            mutate(None, None)

        span = span_exporter.get_finished_spans()[0]
        assert span.attributes["graphql.operation_name"] == "updateTransaction"

    def test_span_has_duration_attribute(
        self, tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        mutate = _make_resolver("deleteGoal")
        with patch("app.extensions.otel.get_tracer", return_value=tracer):
            mutate(None, None)

        span = span_exporter.get_finished_spans()[0]
        assert "graphql.duration_ms" in span.attributes
        assert span.attributes["graphql.duration_ms"] >= 0

    def test_span_has_user_hash_attribute(
        self, tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        mutate = _make_resolver("login")
        with patch("app.extensions.otel.get_tracer", return_value=tracer):
            mutate(None, None)

        span = span_exporter.get_finished_spans()[0]
        assert "auraxis.user_id_hash" in span.attributes


# ---------------------------------------------------------------------------
# Failure path
# ---------------------------------------------------------------------------


class TestSpanOnException:
    def test_span_is_still_recorded_on_exception(
        self, tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        err = ValueError("domain error")
        mutate = _make_resolver("createGoal", raises=err)

        with patch("app.extensions.otel.get_tracer", return_value=tracer):
            with pytest.raises(ValueError, match="domain error"):
                mutate(None, None)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1

    def test_exception_is_recorded_on_span(
        self, tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        err = RuntimeError("unexpected")
        mutate = _make_resolver("deleteWalletEntry", raises=err)

        with patch("app.extensions.otel.get_tracer", return_value=tracer):
            with pytest.raises(RuntimeError):
                mutate(None, None)

        span = span_exporter.get_finished_spans()[0]
        # span.record_exception stores the exception in span events
        event_names = [e.name for e in span.events]
        assert "exception" in event_names

    def test_exception_span_has_error_code_attribute_when_present(
        self, tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        class GqlError(Exception):
            extensions = {"code": "FORBIDDEN"}

        mutate = _make_resolver("updateGoal", raises=GqlError("forbidden"))
        with patch("app.extensions.otel.get_tracer", return_value=tracer):
            with pytest.raises(GqlError):
                mutate(None, None)

        span = span_exporter.get_finished_spans()[0]
        assert span.attributes.get("graphql.error_code") == "FORBIDDEN"


# ---------------------------------------------------------------------------
# No-op safety
# ---------------------------------------------------------------------------


class TestNoOpSafety:
    def test_decorator_works_without_otel_initialised(self) -> None:
        """When get_tracer() returns the global no-op tracer, no exception raised."""
        import app.extensions.otel as otel_mod

        otel_mod.reset_otel_for_tests()
        mutate = _make_resolver("listTransactions")
        result = mutate(None, None)
        assert result == "ok:listTransactions"
