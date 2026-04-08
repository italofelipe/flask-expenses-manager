# mypy: disable-error-code="name-defined"
"""WebhookEvent — persistent audit log for all billing webhook attempts.

Each inbound request to ``POST /subscriptions/webhook`` is logged here
regardless of signature validity, idempotency status, or processing outcome.
This gives full observability into provider call patterns, retry storms, and
failure root-causes without relying on ephemeral application logs.

Statuses
--------
received  — request accepted and awaiting (or currently under) processing.
processed — event applied successfully to the subscription record.
skipped   — known no-op: unsupported event type or duplicate (idempotency).
failed    — processing raised an exception; retry_count tracks attempts.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class WebhookEventStatus(str, enum.Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    SKIPPED = "skipped"
    FAILED = "failed"


class WebhookEvent(db.Model):
    """Immutable audit row for every inbound billing webhook request."""

    __tablename__ = "webhook_events"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    # Provider-level identifiers
    event_id = db.Column(
        db.String(120), nullable=True, index=True
    )  # provider event/idempotency ID
    event_type = db.Column(
        db.String(80), nullable=False
    )  # raw event type string from provider
    provider = db.Column(
        db.String(40), nullable=False
    )  # billing provider name (asaas, stub, …)
    provider_subscription_id = db.Column(db.String(120), nullable=True, index=True)
    provider_customer_id = db.Column(db.String(120), nullable=True)

    # Raw payload stored as TEXT for auditability and replay.
    raw_payload = db.Column(db.Text, nullable=True)  # JSON-serialised request body

    # Security
    signature_verified = db.Column(
        db.Boolean, nullable=False, default=False
    )  # True when HMAC or Asaas token validation passed

    # Processing outcome
    status = db.Column(
        db.Enum(
            "received",
            "processed",
            "skipped",
            "failed",
            name="webhookeventstatus",
        ),
        nullable=False,
        default=WebhookEventStatus.RECEIVED.value,
        index=True,
    )
    failure_reason = db.Column(
        db.String(500), nullable=True
    )  # exception message or rejection reason
    retry_count = db.Column(
        db.Integer, nullable=False, default=0
    )  # number of re-processing attempts

    # Timestamps
    received_at = db.Column(
        db.DateTime, nullable=False, default=utc_now_naive
    )  # UTC when request arrived
    processed_at = db.Column(
        db.DateTime, nullable=True
    )  # UTC when processing completed

    def mark_processed(self, *, now: datetime) -> None:
        self.status = WebhookEventStatus.PROCESSED.value
        self.processed_at = now

    def mark_skipped(self, *, reason: str) -> None:
        self.status = WebhookEventStatus.SKIPPED.value
        self.failure_reason = reason

    def mark_failed(self, *, reason: str, now: datetime) -> None:
        self.status = WebhookEventStatus.FAILED.value
        self.failure_reason = reason[:500]
        self.retry_count += 1
        self.processed_at = now

    def __repr__(self) -> str:
        return (
            f"<WebhookEvent id={self.id} event_type={self.event_type!r} "
            f"status={self.status!r}>"
        )
