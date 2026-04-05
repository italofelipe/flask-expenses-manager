"""add_color_icon_to_tags

Adds color and icon fields to the tags table.

Revision ID: bloco2_color_icon_tags
Revises: bloco2_enrich_models
Create Date: 2026-04-05 00:00:00.000000

Covers:
  - tags: color (String 7, hex), icon (String 50, emoji/key)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "bloco2_color_icon_tags"
down_revision = "bloco2_enrich_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tags",
        sa.Column("color", sa.String(7), nullable=True),
    )
    op.add_column(
        "tags",
        sa.Column("icon", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tags", "icon")
    op.drop_column("tags", "color")
