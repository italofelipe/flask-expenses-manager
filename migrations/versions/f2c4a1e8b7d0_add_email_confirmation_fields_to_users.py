"""add email confirmation fields to users

Revision ID: f2c4a1e8b7d0
Revises: e3b1f6a2d8c9
Create Date: 2026-03-29 13:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f2c4a1e8b7d0"
down_revision = "e3b1f6a2d8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verification_token_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verification_token_expires_at", sa.DateTime(), nullable=True
        ),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_requested_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verification_requested_at")
    op.drop_column("users", "email_verification_token_expires_at")
    op.drop_column("users", "email_verification_token_hash")
