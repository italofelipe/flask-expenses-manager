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
    duration_ms: int
    source_framework: str
    auth_subject: str | None


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


def build_observability_envelope(response: Response) -> ObservabilityEnvelope | None:
    request_context = get_request_context(optional=True)
    if request_context is None:
        return None
    return ObservabilityEnvelope(
        request_id=request_context.request_id,
        route=request_context.endpoint or request_context.path,
        method=request_context.method,
        status_code=response.status_code,
        duration_ms=_resolve_duration_ms(),
        source_framework=request_context.source_framework,
        auth_subject=_resolve_auth_subject(),
    )


def format_observability_log(envelope: ObservabilityEnvelope) -> str:
    return (
        "http_observability request_id=%s route=%s method=%s status=%s "
        "duration_ms=%s source_framework=%s auth_subject=%s"
    ) % (
        envelope.request_id,
        envelope.route,
        envelope.method,
        envelope.status_code,
        envelope.duration_ms,
        envelope.source_framework,
        envelope.auth_subject or "anonymous",
    )


__all__ = [
    "ObservabilityEnvelope",
    "build_observability_envelope",
    "format_observability_log",
    "mark_request_start",
]
