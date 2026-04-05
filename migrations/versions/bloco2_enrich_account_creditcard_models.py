"""enrich_account_creditcard_models

Adds financial enrichment fields to accounts and credit_cards tables.

Revision ID: bloco2_enrich_models
Revises: b21_perf_indexes
Create Date: 2026-04-05 00:00:00.000000

Covers:
  - accounts: account_type, institution, initial_balance
  - credit_cards: brand, limit_amount, closing_day, due_day, last_four_digits
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "bloco2_enrich_models"
down_revision = "b21_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # accounts
    # -----------------------------------------------------------------------
    op.add_column(
        "accounts",
        sa.Column(
            "account_type",
            sa.String(20),
            nullable=False,
            server_default="checking",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column("institution", sa.String(100), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "initial_balance",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )

    # -----------------------------------------------------------------------
    # credit_cards
    # -----------------------------------------------------------------------
    op.add_column(
        "credit_cards",
        sa.Column("brand", sa.String(20), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column("limit_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column("closing_day", sa.Integer(), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column("due_day", sa.Integer(), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column("last_four_digits", sa.String(4), nullable=True),
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # credit_cards
    # -----------------------------------------------------------------------
    op.drop_column("credit_cards", "last_four_digits")
    op.drop_column("credit_cards", "due_day")
    op.drop_column("credit_cards", "closing_day")
    op.drop_column("credit_cards", "limit_amount")
    op.drop_column("credit_cards", "brand")

    # -----------------------------------------------------------------------
    # accounts
    # -----------------------------------------------------------------------
    op.drop_column("accounts", "initial_balance")
    op.drop_column("accounts", "institution")
    op.drop_column("accounts", "account_type")
