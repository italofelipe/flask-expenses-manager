from __future__ import annotations

import os
import threading
from time import monotonic
from typing import Any

from flask import Flask, Response, current_app, g, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions.database import db
from app.models.audit_event import AuditEvent
from app.services.audit_event_service import purge_expired_audit_events

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


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


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


class _AuditRetentionRunner:
    def __init__(self, *, retention_days: int, interval_seconds: int) -> None:
        self._retention_days = max(retention_days, 1)
        self._interval_seconds = max(interval_seconds, 60)
        self._lock = threading.Lock()
        self._next_run_at = 0.0

    def maybe_run(self) -> None:
        now = monotonic()
        if now < self._next_run_at:
            return
        with self._lock:
            now = monotonic()
            if now < self._next_run_at:
                return
            self._next_run_at = now + self._interval_seconds
            deleted = purge_expired_audit_events(retention_days=self._retention_days)
            if deleted > 0:
                current_app.logger.info(
                    "audit_retention_prune_deleted count=%s retention_days=%s",
                    deleted,
                    self._retention_days,
                )


def register_audit_trail(app: Flask) -> None:
    if not _is_audit_trail_enabled():
        return

    prefixes = _load_path_prefixes()

    retention_runner: _AuditRetentionRunner | None = None
    if _is_audit_persistence_enabled() and _is_audit_retention_enabled():
        retention_runner = _AuditRetentionRunner(
            retention_days=_read_int_env("AUDIT_RETENTION_DAYS", 90),
            interval_seconds=_read_int_env(
                "AUDIT_RETENTION_SWEEP_INTERVAL_SECONDS",
                3600,
            ),
        )

    @app.after_request  # type: ignore[misc]
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
            if retention_runner is not None:
                retention_runner.maybe_run()
        return response
