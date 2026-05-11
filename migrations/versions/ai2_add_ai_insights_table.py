"""Add ai_insights table (#1227).

Revision ID: ai2
Revises: ai1
Create Date: 2026-05-11

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ai2"
down_revision = "ai1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_insights",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "insight_type",
            sa.String(length=20),
            sa.CheckConstraint(
                "insight_type IN ('daily','weekly','monthly','recap')",
                name="ck_ai_insights_type",
            ),
            nullable=False,
        ),
        sa.Column("period_label", sa.String(length=30), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "previous_insight_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_insights.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_ai_insights_user_id", "ai_insights", ["user_id"])
    op.create_index(
        "ix_ai_insights_user_created", "ai_insights", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_ai_insights_user_type_period",
        "ai_insights",
        ["user_id", "insight_type", "period_label"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_insights_user_type_period", table_name="ai_insights")
    op.drop_index("ix_ai_insights_user_created", table_name="ai_insights")
    op.drop_index("ix_ai_insights_user_id", table_name="ai_insights")
    op.drop_table("ai_insights")
