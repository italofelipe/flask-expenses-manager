"""Framework-agnostic request metadata boundary.

During the Flask -> FastAPI coexistence window this module is the canonical
entrypoint for request metadata consumed outside HTTP adapters.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, overload
from uuid import uuid4

from flask import Flask, Response, g, has_request_context, request

# Allow only safe characters in inbound X-Request-ID to prevent log injection.
_REQUEST_ID_SAFE_RE = re.compile(r"^[a-zA-Z0-9\-_.]{1,128}$")


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    method: str
    path: str
    endpoint: str | None
    client_ip: str | None
    user_agent: str | None
    headers: Mapping[str, str]
    trace_id: str | None
    source_framework: Literal["flask", "fastapi"]


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalized_headers() -> dict[str, str]:
    return {
        str(key).lower(): str(value)
        for key, value in request.headers.items()
        if isinstance(key, str)
    }


def _resolve_client_ip(headers: Mapping[str, str]) -> str | None:
    trust_proxy = _read_bool_env("REQUEST_CONTEXT_TRUST_PROXY_HEADERS", True)
    if trust_proxy:
        forwarded_for = str(headers.get("x-forwarded-for", "")).strip()
        if forwarded_for:
            first_hop = forwarded_for.split(",")[0].strip()
            if first_hop:
                return first_hop
        real_ip = str(headers.get("x-real-ip", "")).strip()
        if real_ip:
            return real_ip
    remote_addr = request.remote_addr
    return str(remote_addr) if remote_addr else None


def _resolve_trace_id(headers: Mapping[str, str]) -> str | None:
    for key in ("x-trace-id", "traceparent", "x-request-id"):
        value = str(headers.get(key, "")).strip()
        if value:
            return value[:512]
    return None


def _build_request_context() -> RequestContext:
    headers = _normalized_headers()
    request_id = str(getattr(g, "request_id", "") or uuid4().hex)
    g.request_id = request_id
    return RequestContext(
        request_id=request_id,
        method=request.method,
        path=request.path,
        endpoint=request.endpoint,
        client_ip=_resolve_client_ip(headers),
        user_agent=str(headers.get("user-agent", "")).strip() or None,
        headers=headers,
        trace_id=_resolve_trace_id(headers),
        source_framework="flask",
    )


def _sanitize_inbound_request_id(value: str) -> str:
    """Return value if it is safe to use as a request_id, else empty string."""
    value = value.strip()
    return value if _REQUEST_ID_SAFE_RE.match(value) else ""


def bind_request_context() -> None:
    # Honor an X-Request-ID forwarded by nginx ($request_id) or a frontend
    # client so the same ID is traceable end-to-end.  Sanitise before storing.
    incoming = _sanitize_inbound_request_id(request.headers.get("X-Request-ID", ""))
    g.request_id = incoming or uuid4().hex
    g.request_context = _build_request_context()


def apply_request_context_headers(response: Response) -> Response:
    response.headers["X-Request-Id"] = current_request_id(default="n/a")
    return response


@overload
def get_request_context(*, optional: Literal[False] = False) -> RequestContext: ...


@overload
def get_request_context(*, optional: Literal[True]) -> RequestContext | None: ...


def get_request_context(*, optional: bool = False) -> RequestContext | None:
    if not has_request_context():
        if optional:
            return None
        raise RuntimeError("Active request context is required.")
    cached = getattr(g, "request_context", None)
    if isinstance(cached, RequestContext):
        return cached
    context = _build_request_context()
    g.request_context = context
    return context


def current_request_id(*, default: str = "n/a") -> str:
    context = get_request_context(optional=True)
    if context is None:
        return default
    return context.request_id


def register_request_context_adapter(app: Flask) -> None:
    @app.before_request
    def _bind_request_context() -> None:
        bind_request_context()

    @app.after_request
    def _append_request_id_header(response: Response) -> Response:
        return apply_request_context_headers(response)


__all__ = [
    "RequestContext",
    "apply_request_context_headers",
    "bind_request_context",
    "current_request_id",
    "get_request_context",
    "register_request_context_adapter",
]
