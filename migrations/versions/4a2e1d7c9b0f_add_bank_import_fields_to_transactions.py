"""add bank import foundation fields to transactions

Revision ID: 4a2e1d7c9b0f
Revises: 3d6f4c2b1a9e
Create Date: 2026-03-26 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4a2e1d7c9b0f"
down_revision = "3d6f4c2b1a9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "source",
            sa.String(length=40),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("external_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("bank_name", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_transactions_user_source",
        "transactions",
        ["user_id", "source"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_transactions_user_external_id",
        "transactions",
        ["user_id", "external_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_transactions_user_external_id",
        "transactions",
        type_="unique",
    )
    op.drop_index("ix_transactions_user_source", table_name="transactions")
    op.drop_column("transactions", "bank_name")
    op.drop_column("transactions", "external_id")
    op.drop_column("transactions", "source")
