from __future__ import annotations

import os
from typing import Optional

import click
from flask import Flask

from app.services.audit_event_service import purge_expired_audit_events


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


def _resolve_retention_days(cli_value: Optional[int]) -> int:
    if cli_value is None:
        return _read_int_env("AUDIT_RETENTION_DAYS", 90)
    return max(int(cli_value), 1)


def register_audit_retention_commands(app: Flask) -> None:
    @app.cli.group("audit-events")
    def audit_events_group() -> None:
        """Operational commands for persisted audit events."""

    @audit_events_group.command("purge-expired")
    @click.option(
        "--retention-days",
        type=int,
        default=None,
        help="Retention window in days (defaults to AUDIT_RETENTION_DAYS).",
    )
    def purge_expired_command(retention_days: Optional[int]) -> None:
        if not _is_audit_retention_enabled():
            click.echo("audit retention disabled (AUDIT_RETENTION_ENABLED=false)")
            return

        effective_retention_days = _resolve_retention_days(retention_days)
        deleted = purge_expired_audit_events(retention_days=effective_retention_days)
        click.echo(
            f"deleted={deleted} retention_days={effective_retention_days}",
        )
