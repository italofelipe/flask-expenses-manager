"""recurrence_cadence

Adds configurable recurrence cadence to `transactions`:

- recurrence_interval (INT, NOT NULL, default 1)
- recurrence_unit     (VARCHAR, NOT NULL, default 'month')

Together they express "repeat every N units" (e.g. interval=2 + unit=week →
every two weeks). Legacy recurring rows default to a monthly cadence so they
keep materialising as before.

`recurrence_unit` is stored as VARCHAR (matching the model's
`Enum(..., native_enum=False)`) — no native PG enum / CREATE TYPE, per the
repo migration conventions.

Revision ID: rec1_recurrence_cadence
Revises: ai6_add_ai_insight_runs
Create Date: 2026-05-30 00:00:00.000000

Refs: #1384 (auraxis-api).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "rec1_recurrence_cadence"
down_revision = "ai6_add_ai_insight_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "recurrence_interval",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "recurrence_unit",
            sa.String(length=10),
            nullable=False,
            server_default="month",
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "recurrence_unit")
    op.drop_column("transactions", "recurrence_interval")
