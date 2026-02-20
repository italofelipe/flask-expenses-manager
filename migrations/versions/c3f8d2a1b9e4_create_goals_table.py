"""create goals table

Revision ID: c3f8d2a1b9e4
Revises: 69f75d73808e
Create Date: 2026-02-20 10:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3f8d2a1b9e4"
down_revision = "69f75d73808e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("target_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "current_amount",
            sa.Numeric(precision=12, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), server_default="3", nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column(
            "status", sa.String(length=24), server_default="active", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("target_amount >= 0", name="ck_goals_target_amount_nonneg"),
        sa.CheckConstraint(
            "current_amount >= 0",
            name="ck_goals_current_amount_nonneg",
        ),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_goals_priority"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"], unique=False)
    op.create_index("ix_goals_status", "goals", ["status"], unique=False)
    op.create_index("ix_goals_target_date", "goals", ["target_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_goals_target_date", table_name="goals")
    op.drop_index("ix_goals_status", table_name="goals")
    op.drop_index("ix_goals_user_id", table_name="goals")
    op.drop_table("goals")
