"""push1 — create push_subscriptions table

Revision ID: push1
Revises: avt1
Create Date: 2026-05-07

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "push1"
down_revision = "avt1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent enum creation — safe even if the type was partially created
    # by a prior failed migration attempt or by SQLAlchemy model introspection.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "  CREATE TYPE push_transport_enum AS ENUM ('web_push', 'expo'); "
            "EXCEPTION WHEN duplicate_object THEN null; "
            "END $$"
        )
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transport",
            sa.Enum("web_push", "expo", name="push_transport_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("keys", sa.JSON, nullable=True),
        sa.Column("expiration_time", sa.DateTime, nullable=True),
        sa.Column("device_label", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_push_subscriptions_user_id",
        "push_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "uq_push_subscriptions_user_transport_endpoint",
        "push_subscriptions",
        ["user_id", "transport", "endpoint"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_push_subscriptions_user_transport_endpoint")
    op.drop_index("ix_push_subscriptions_user_id")
    op.drop_table("push_subscriptions")
    op.execute("DROP TYPE IF EXISTS push_transport_enum")
