"""push1 — create push_subscriptions table

Revision ID: push1
Revises: avt1
Create Date: 2026-05-06

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "push1"
down_revision = "avt1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    transport_enum = postgresql.ENUM(
        "web_push", "expo", name="push_transport_enum", create_type=True
    )
    transport_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "push_subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transport",
            sa.Enum("web_push", "expo", name="push_transport_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("keys", postgresql.JSONB, nullable=True),
        sa.Column("expiration_time", sa.DateTime, nullable=True),
        sa.Column("device_label", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False
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
    op.drop_table("push_subscriptions")
    op.execute("DROP TYPE IF EXISTS push_transport_enum")
