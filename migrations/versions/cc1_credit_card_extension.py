"""credit_card_extension

Adds enrichment fields to credit_cards table for the Credit Cards Hub MVP-3:
bank, description, benefits (JSON-encoded list in Text), validity_date,
created_at, updated_at.

All fields are nullable or have server_default so no backfill is required and
the migration is safe to deploy without downtime.

Revision ID: cc1_credit_card_extension
Revises: cons1
Create Date: 2026-05-17 16:00:00.000000

Refs: #1284 (auraxis-api), MVP-3 wiki (auraxis-platform).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "cc1_credit_card_extension"
down_revision = "cons1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credit_cards",
        sa.Column("bank", sa.String(80), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column("description", sa.String(300), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column("benefits", sa.Text(), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column("validity_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "credit_cards",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "credit_cards",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("credit_cards", "updated_at")
    op.drop_column("credit_cards", "created_at")
    op.drop_column("credit_cards", "validity_date")
    op.drop_column("credit_cards", "benefits")
    op.drop_column("credit_cards", "description")
    op.drop_column("credit_cards", "bank")
