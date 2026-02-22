"""add password reset fields to users

Revision ID: e3b1f6a2d8c9
Revises: b8_add_user_profile_fields
Create Date: 2026-02-22 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e3b1f6a2d8c9"
down_revision = "b8_add_user_profile_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("password_reset_token_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_reset_token_expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_reset_requested_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("users", "password_reset_requested_at")
    op.drop_column("users", "password_reset_token_expires_at")
    op.drop_column("users", "password_reset_token_hash")
