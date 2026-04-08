"""add webhook_events audit table (PAY-03)

Revision ID: p916_webhook_events
Revises: j618_foundation
Create Date: 2026-04-08 00:00:00.000000

Covers GH #916 / #917 (PAY-02/PAY-03):
  - webhook_events: persistent audit log for all billing webhook attempts
    with status tracking and retry counter for failed events.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p916_webhook_events"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        # Provider identifiers
        sa.Column("event_id", sa.String(120), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_subscription_id", sa.String(120), nullable=True),
        sa.Column("provider_customer_id", sa.String(120), nullable=True),
        # Payload
        sa.Column("raw_payload", sa.Text, nullable=True),
        # Security
        sa.Column(
            "signature_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Processing outcome
        sa.Column(
            "status",
            sa.Enum(
                "received",
                "processed",
                "skipped",
                "failed",
                name="webhookeventstatus",
            ),
            nullable=False,
            server_default="received",
        ),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        # Timestamps
        sa.Column("received_at", sa.DateTime, nullable=False),
        sa.Column("processed_at", sa.DateTime, nullable=True),
    )

    # Indexes for operational queries
    op.create_index(
        "ix_webhook_events_event_id",
        "webhook_events",
        ["event_id"],
    )
    op.create_index(
        "ix_webhook_events_provider_subscription_id",
        "webhook_events",
        ["provider_subscription_id"],
    )
    op.create_index(
        "ix_webhook_events_status",
        "webhook_events",
        ["status"],
    )
    # Partial index for failed events that need retry — most queries filter here.
    op.create_index(
        "ix_webhook_events_failed_retry",
        "webhook_events",
        ["received_at"],
        postgresql_where=sa.text("status = 'failed'"),
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_events_failed_retry", table_name="webhook_events")
    op.drop_index("ix_webhook_events_status", table_name="webhook_events")
    op.drop_index(
        "ix_webhook_events_provider_subscription_id", table_name="webhook_events"
    )
    op.drop_index("ix_webhook_events_event_id", table_name="webhook_events")
    op.drop_table("webhook_events")
    op.execute("DROP TYPE IF EXISTS webhookeventstatus")
