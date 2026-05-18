"""Flask CLI commands for billing webhook operational management (PAY-03)."""

from __future__ import annotations

import logging
from typing import Any

import click
from flask import Flask

logger = logging.getLogger(__name__)


def _retry_single_event(event: Any) -> tuple[bool, str | None]:
    """Process one failed webhook event. Returns (processed, error_message)."""
    import json as _json

    from app.controllers.subscription_controller import (
        _extract_event_id,
        _extract_provider_snapshot,
        _process_webhook_snapshot,
    )
    from app.extensions.database import db
    from app.utils.datetime_utils import utc_now_naive

    if not event.raw_payload:
        event.mark_failed(reason="missing_raw_payload", now=utc_now_naive())
        db.session.commit()
        return False, "missing_raw_payload"

    try:
        payload: dict[str, Any] = _json.loads(event.raw_payload)
    except Exception as exc:
        event.mark_failed(reason=f"payload_parse_error:{exc}", now=utc_now_naive())
        db.session.commit()
        return False, f"payload_parse_error:{exc}"

    snapshot = _extract_provider_snapshot(payload)
    if snapshot is None:
        event.mark_failed(
            reason="unresolvable_subscription_on_retry", now=utc_now_naive()
        )
        db.session.commit()
        return False, "unresolvable_subscription_on_retry"

    event_type: str = payload.get("event", "")
    event_id = _extract_event_id(payload)

    try:
        _process_webhook_snapshot(event_type, event_id, snapshot, event)
        return True, None
    except Exception as exc:
        event.mark_failed(reason=str(exc), now=utc_now_naive())
        db.session.commit()
        logger.exception(
            "billing-webhooks retry-failed: error reprocessing event id=%s",
            event.id,
        )
        return False, str(exc)


def register_billing_webhooks_commands(app: Flask) -> None:
    @app.cli.group("billing-webhooks")
    def billing_webhooks_group() -> None:
        """Operational commands for billing webhook events."""

    @billing_webhooks_group.command("retry-failed")
    @click.option(
        "--max-events",
        default=50,
        show_default=True,
        type=int,
        help="Maximum number of failed events to retry in a single run.",
    )
    @click.option(
        "--max-retries",
        default=3,
        show_default=True,
        type=int,
        help="Skip events that have already been retried this many times.",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Log eligible events without reprocessing them.",
    )
    def retry_failed(max_events: int, max_retries: int, dry_run: bool) -> None:
        """Retry webhook events that failed during processing.

        Reprocesses up to ``--max-events`` events whose status is ``failed``
        and whose ``retry_count`` is below ``--max-retries``.  Each successful
        retry updates the event status to ``processed``; each new failure
        increments ``retry_count`` and keeps status ``failed``.
        """
        from app.extensions.database import db
        from app.models.webhook_event import WebhookEvent, WebhookEventStatus

        eligible = (
            db.session.query(WebhookEvent)
            .filter(
                WebhookEvent.status == WebhookEventStatus.FAILED.value,
                WebhookEvent.retry_count < max_retries,
            )
            .order_by(WebhookEvent.received_at.asc())
            .limit(max_events)
            .all()
        )

        if not eligible:
            click.echo("billing-webhooks retry-failed: no eligible events found.")
            return

        click.echo(
            f"billing-webhooks retry-failed: {len(eligible)} event(s) eligible "
            f"(dry_run={dry_run})."
        )

        processed_count = 0
        failed_count = 0

        for event in eligible:
            click.echo(
                f"  event id={event.id} event_type={event.event_type!r} "
                f"retry_count={event.retry_count}"
            )
            if dry_run:
                continue
            processed, error = _retry_single_event(event)
            if processed:
                processed_count += 1
                click.echo("    → processed")
            else:
                failed_count += 1
                click.echo(f"    → failed: {error}")

        click.echo(
            f"billing-webhooks retry-failed: done — "
            f"processed={processed_count} failed={failed_count} "
            f"skipped_dry_run={len(eligible) if dry_run else 0}"
        )
