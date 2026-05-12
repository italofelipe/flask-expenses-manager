"""Add goal_contributions table (#1234).

Revision ID: ai3
Revises: ai2
Create Date: 2026-05-12

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ai3"
down_revision = "ai2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goal_contributions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "goal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("goals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_goal_contributions_user_goal",
        "goal_contributions",
        ["user_id", "goal_id"],
    )
    op.create_index(
        "ix_goal_contributions_user_created",
        "goal_contributions",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_goal_contributions_user_created", table_name="goal_contributions")
    op.drop_index("ix_goal_contributions_user_goal", table_name="goal_contributions")
    op.drop_table("goal_contributions")
