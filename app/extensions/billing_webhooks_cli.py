"""Flask CLI commands for billing webhook operational management (PAY-03)."""

from __future__ import annotations

import logging
from typing import Any

import click
from flask import Flask

logger = logging.getLogger(__name__)


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
        import json as _json

        from app.controllers.subscription_controller import (
            _extract_provider_snapshot,
            _process_webhook_snapshot,
        )
        from app.extensions.database import db
        from app.models.webhook_event import WebhookEvent, WebhookEventStatus
        from app.utils.datetime_utils import utc_now_naive

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

            if not event.raw_payload:
                event.mark_failed(reason="missing_raw_payload", now=utc_now_naive())
                db.session.commit()
                failed_count += 1
                continue

            try:
                payload: dict[str, Any] = _json.loads(event.raw_payload)
            except Exception as exc:
                event.mark_failed(
                    reason=f"payload_parse_error:{exc}", now=utc_now_naive()
                )
                db.session.commit()
                failed_count += 1
                continue

            snapshot = _extract_provider_snapshot(payload)
            if snapshot is None:
                event.mark_failed(
                    reason="unresolvable_subscription_on_retry", now=utc_now_naive()
                )
                db.session.commit()
                failed_count += 1
                continue

            event_type: str = payload.get("event", "")
            from app.controllers.subscription_controller import _extract_event_id

            event_id = _extract_event_id(payload)

            try:
                _process_webhook_snapshot(event_type, event_id, snapshot, event)
                processed_count += 1
                click.echo("    → processed")
            except Exception as exc:
                event.mark_failed(reason=str(exc), now=utc_now_naive())
                db.session.commit()
                failed_count += 1
                logger.exception(
                    "billing-webhooks retry-failed: error reprocessing event id=%s",
                    event.id,
                )
                click.echo(f"    → failed: {exc}")

        click.echo(
            f"billing-webhooks retry-failed: done — "
            f"processed={processed_count} failed={failed_count} "
            f"skipped_dry_run={len(eligible) if dry_run else 0}"
        )
