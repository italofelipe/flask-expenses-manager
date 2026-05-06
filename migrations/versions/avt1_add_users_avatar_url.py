"""add users.avatar_url

Revision ID: avt1
Revises: sim1
Create Date: 2026-05-06

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "avt1"
down_revision = "sim1_simulations_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
