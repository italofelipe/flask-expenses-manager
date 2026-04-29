"""SIM-1 — Generic simulations: add metadata column + (user_id, tool_id, created_at) index.

Supports the canonical generic POST /simulations endpoint (issue #1128 /
DEC-196). The endpoint persists simulations from any tool in TOOLS_REGISTRY
into the existing ``simulations`` table.

Two changes:

1. Add nullable ``metadata`` JSONB column for optional user-supplied label/notes
   ("Cenário conservador", etc.). The Python attribute is named
   ``extra_metadata`` to avoid colliding with SQLAlchemy's reserved
   ``Model.metadata``; the column on the DB stays as ``metadata``.

2. Add composite index ``ix_simulations_user_tool_created`` to support the new
   query pattern (filter by user_id + tool_id, ordered by created_at desc) used
   by the generic list endpoint with the optional ``tool_id`` filter.

Both operations are idempotent (``if_not_exists=True``) so re-applying on a
prod DB that received a hotfix is safe.

Revision ID: sim1_simulations_metadata
Revises: hd1054_merge_1053_heads
Create Date: 2026-04-29 12:40:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "sim1_simulations_metadata"
down_revision = "hd1054_merge_1053_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulations",
        sa.Column(
            "metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_simulations_user_tool_created",
        "simulations",
        ["user_id", "tool_id", "created_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_simulations_user_tool_created",
        table_name="simulations",
        if_exists=True,
    )
    op.drop_column("simulations", "metadata")
