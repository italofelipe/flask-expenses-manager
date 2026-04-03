"""add refresh_token_jti to users

Revision ID: b18_refresh_token_jti
Revises: f2c4a1e8b7d0
Create Date: 2026-04-03 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "b18_refresh_token_jti"
down_revision = "f2c4a1e8b7d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("refresh_token_jti", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "refresh_token_jti")
