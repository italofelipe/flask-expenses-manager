"""add deleted_at to users for LGPD soft-delete

Merges the pre-existing branch heads (f2c4a1e8b7d0, a1b2c3d4e5f6,
bloco2_color_icon_tags) back to a single head while adding the new column.

Revision ID: b885_add_deleted_at_to_users
Revises: f2c4a1e8b7d0, a1b2c3d4e5f6, bloco2_color_icon_tags
Create Date: 2026-04-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b885_add_deleted_at_to_users"
down_revision = ("f2c4a1e8b7d0", "a1b2c3d4e5f6", "bloco2_color_icon_tags")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
