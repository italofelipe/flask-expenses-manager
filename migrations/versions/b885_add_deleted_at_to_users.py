"""add deleted_at to users for LGPD soft-delete

Adds a nullable deleted_at column to the users table to support
LGPD-compliant soft deletion via DELETE /user/me.

Revision ID: b885_add_deleted_at_to_users
Revises: bloco2_color_icon_tags
Create Date: 2026-04-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b885_add_deleted_at_to_users"
down_revision = "bloco2_color_icon_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
