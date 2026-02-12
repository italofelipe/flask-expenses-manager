from __future__ import annotations

import os
from typing import Any

from flask import Flask, Response, current_app, g, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions.database import db
from app.models.audit_event import AuditEvent

DEFAULT_AUDIT_PATH_PREFIXES = (
    "/auth/",
    "/user/",
    "/transactions/",
    "/wallet",
    "/graphql",
)


def _is_audit_trail_enabled() -> bool:
    return os.getenv("AUDIT_TRAIL_ENABLED", "true").lower() == "true"


def _is_audit_persistence_enabled() -> bool:
    return os.getenv("AUDIT_PERSISTENCE_ENABLED", "false").lower() == "true"


def _is_audit_retention_enabled() -> bool:
    return os.getenv("AUDIT_RETENTION_ENABLED", "true").lower() == "true"


def _load_path_prefixes() -> tuple[str, ...]:
    raw = os.getenv("AUDIT_PATH_PREFIXES", "")
    if not raw.strip():
        return DEFAULT_AUDIT_PATH_PREFIXES
    items = tuple(item.strip() for item in raw.split(",") if item.strip())
    return items or DEFAULT_AUDIT_PATH_PREFIXES


def _is_sensitive_path(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _extract_user_id_safely() -> str | None:
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity is None:
            return None
        return str(identity)
    except Exception:
        return None


def _extract_client_ip() -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        first_hop = forwarded_for.split(",")[0].strip()
        return first_hop or None
    remote_addr = request.remote_addr
    return str(remote_addr) if remote_addr else None


def _build_event_payload(response: Response) -> dict[str, Any]:
    return {
        "event": "http.audit",
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "request_id": getattr(g, "request_id", None),
        "user_id": _extract_user_id_safely(),
        "ip": _extract_client_ip(),
        "user_agent": request.headers.get("User-Agent", ""),
    }


def _persist_audit_event(payload: dict[str, Any]) -> None:
    try:
        event = AuditEvent(
            request_id=payload.get("request_id"),
            method=str(payload.get("method", "")),
            path=str(payload.get("path", "")),
            status=int(payload.get("status", 0)),
            user_id=payload.get("user_id"),
            ip=payload.get("ip"),
            user_agent=payload.get("user_agent"),
        )
        db.session.add(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("audit_persistence_failed")


def _log_retention_strategy(
    app: Flask,
    *,
    persistence_enabled: bool,
    retention_enabled: bool,
) -> None:
    if not persistence_enabled or not retention_enabled:
        return
    app.logger.info(
        "audit_retention_mode=external_job command='flask audit-events purge-expired'",
    )


def register_audit_trail(app: Flask) -> None:
    if not _is_audit_trail_enabled():
        return

    prefixes = _load_path_prefixes()
    retention_enabled = _is_audit_retention_enabled()
    _log_retention_strategy(
        app,
        persistence_enabled=_is_audit_persistence_enabled(),
        retention_enabled=retention_enabled,
    )

    @app.after_request
    def _emit_audit_event(response: Response) -> Response:
        if request.method == "OPTIONS":
            return response
        if not _is_sensitive_path(request.path, prefixes):
            return response

        payload = _build_event_payload(response)
        endpoint = request.endpoint or "unknown"
        message = (
            "audit_trail event=http.audit method=%s endpoint=%s "
            "status=%s request_id=%s"
        )
        current_app.logger.info(
            message,
            request.method,
            endpoint,
            response.status_code,
            getattr(g, "request_id", None),
        )
        if _is_audit_persistence_enabled():
            _persist_audit_event(payload)
        return response
