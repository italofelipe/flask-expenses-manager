from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from flask import Response, g

from app.auth import get_current_auth_context
from app.http.request_context import get_request_context


@dataclass(frozen=True)
class ObservabilityEnvelope:
    request_id: str
    route: str
    method: str
    status_code: int
    status_class: str
    is_error: bool
    duration_ms: int
    source_framework: str
    trace_id: str | None
    auth_subject: str | None
    graphql_operation_name: str | None
    graphql_root_fields: tuple[str, ...]


def mark_request_start() -> None:
    g.request_started_at = perf_counter()


def _resolve_duration_ms() -> int:
    started_at = getattr(g, "request_started_at", None)
    if not isinstance(started_at, float):
        return 0
    duration_ms = int(round((perf_counter() - started_at) * 1000))
    return max(duration_ms, 0)


def _resolve_auth_subject() -> str | None:
    try:
        context = get_current_auth_context(optional=True)
    except Exception:
        return None
    if context is None:
        return None
    return context.subject


def _resolve_status_class(status_code: int) -> str:
    if 100 <= status_code < 200:
        return "1xx"
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    return "5xx"


def _resolve_graphql_root_fields() -> tuple[str, ...]:
    raw_fields = getattr(g, "graphql_root_fields", ())
    if not isinstance(raw_fields, (tuple, list)):
        return ()
    resolved = [
        str(field).strip()
        for field in raw_fields
        if isinstance(field, str) and str(field).strip()
    ]
    return tuple(resolved)


def build_observability_envelope(response: Response) -> ObservabilityEnvelope | None:
    request_context = get_request_context(optional=True)
    if request_context is None:
        return None
    status_class = _resolve_status_class(response.status_code)
    return ObservabilityEnvelope(
        request_id=request_context.request_id,
        route=request_context.endpoint or request_context.path,
        method=request_context.method,
        status_code=response.status_code,
        status_class=status_class,
        is_error=response.status_code >= 400,
        duration_ms=_resolve_duration_ms(),
        source_framework=request_context.source_framework,
        trace_id=request_context.trace_id,
        auth_subject=_resolve_auth_subject(),
        graphql_operation_name=(
            str(getattr(g, "graphql_operation_name", "")).strip() or None
        ),
        graphql_root_fields=_resolve_graphql_root_fields(),
    )


def format_observability_log(envelope: ObservabilityEnvelope) -> str:
    return (
        "http_observability request_id=%s trace_id=%s route=%s method=%s status=%s "
        "status_class=%s is_error=%s duration_ms=%s source_framework=%s "
        "auth_subject=%s graphql_operation=%s graphql_root_fields=%s"
    ) % (
        envelope.request_id,
        envelope.trace_id or "n/a",
        envelope.route,
        envelope.method,
        envelope.status_code,
        envelope.status_class,
        str(envelope.is_error).lower(),
        envelope.duration_ms,
        envelope.source_framework,
        envelope.auth_subject or "anonymous",
        envelope.graphql_operation_name or "n/a",
        ",".join(envelope.graphql_root_fields) or "n/a",
    )


__all__ = [
    "ObservabilityEnvelope",
    "build_observability_envelope",
    "format_observability_log",
    "mark_request_start",
]
