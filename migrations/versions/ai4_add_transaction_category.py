"""Add category column to transactions (#1239).

Revision ID: ai4
Revises: ai3
Create Date: 2026-05-12

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ai4"
down_revision = "ai3"
branch_labels = None
depends_on = None

_VALID_CATEGORIES = (
    "alimentacao",
    "transporte",
    "moradia",
    "saude",
    "lazer",
    "educacao",
    "investimentos",
    "poupanca",
    "outros",
)


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "category",
            sa.String(length=20),
            sa.CheckConstraint(
                f"category IN {_VALID_CATEGORIES!r} OR category IS NULL",
                name="ck_transactions_category",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_transactions_user_category",
        "transactions",
        ["user_id", "category"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_category", table_name="transactions")
    op.drop_column("transactions", "category")
