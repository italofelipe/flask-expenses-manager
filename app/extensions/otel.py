"""OpenTelemetry tracing initialisation for auraxis-api.

Call ``init_otel(app)`` once at application startup (inside ``create_app()``).
The integration is a no-op when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is absent or
empty, so local development and test runs are never affected.

Required env vars:
    OTEL_EXPORTER_OTLP_ENDPOINT — OTLP HTTP endpoint (absent = disabled)

Optional env vars:
    OTEL_SERVICE_NAME        — service name exported in spans (default: "auraxis-api")
    OTEL_TRACES_SAMPLER      — sampler type (default: "parentbased_traceidratio")
    OTEL_TRACES_SAMPLER_ARG  — sampler rate 0-1 (default: "0.1" = 10 % of traces)

Usage
-----
Graphene resolvers:
    from app.extensions.otel import get_tracer

    tracer = get_tracer()
    with tracer.start_as_current_span("graphql.myMutation") as span:
        span.set_attribute("graphql.operation_name", "myMutation")
        ...

GraphQL middleware automatically creates operation-level spans when
``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.  The existing
``log_graphql_resolver`` decorator also emits a child span per resolver.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask

# Module-level singleton so `get_tracer()` is always safe to call.
_tracer: Any = None
_sdk_initialized: bool = False


def _build_sampler() -> Any:
    """Build a sampler from env vars; always returns a valid sampler."""
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )

    sampler_type = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio")
    sampler_arg = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))

    if sampler_type == "always_on":
        return ALWAYS_ON
    if sampler_type == "traceidratio":
        return TraceIdRatioBased(sampler_arg)
    # Default: parentbased_traceidratio — defers to parent when available.
    return ParentBased(root=TraceIdRatioBased(sampler_arg))


def init_otel(app: Flask) -> None:
    """Initialise the OpenTelemetry SDK.

    No-op when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset.  Safe to call
    multiple times inside the same process (subsequent calls are no-ops).
    """
    global _tracer, _sdk_initialized  # noqa: PLW0603

    if _sdk_initialized:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        # Provide a no-op tracer so call sites never need to guard.
        from opentelemetry import trace

        _tracer = trace.get_tracer(__name__)
        _sdk_initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.getenv("OTEL_SERVICE_NAME", "auraxis-api")
        resource = Resource(attributes={SERVICE_NAME: service_name})

        provider = TracerProvider(resource=resource, sampler=_build_sampler())
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        trace.set_tracer_provider(provider)

        FlaskInstrumentor().instrument_app(app)  # type: ignore[no-untyped-call]

        # SQLAlchemy engine is available after the app context is set up.
        from app.extensions.database import db

        SQLAlchemyInstrumentor().instrument(engine=db.engine)

        _tracer = trace.get_tracer(__name__)
        _sdk_initialized = True

        app.logger.info(
            "OpenTelemetry tracing enabled endpoint=%s service=%s",
            endpoint,
            service_name,
        )

    except Exception:  # noqa: BLE001
        app.logger.warning(
            "OpenTelemetry initialisation failed — tracing disabled.",
            exc_info=True,
        )
        from opentelemetry import trace

        _tracer = trace.get_tracer(__name__)
        _sdk_initialized = True


def get_tracer() -> Any:
    """Return the module-level OpenTelemetry tracer (always safe to call).

    Returns a no-op tracer when OTel is not initialised.
    """
    global _tracer  # noqa: PLW0603

    if _tracer is None:
        from opentelemetry import trace

        _tracer = trace.get_tracer(__name__)
    return _tracer


def reset_otel_for_tests() -> None:
    """Reset singleton state so tests can reinitialise with a custom provider."""
    global _tracer, _sdk_initialized  # noqa: PLW0603
    _tracer = None
    _sdk_initialized = False
