"""Add invitation token and expiry columns.

Revision ID: 7f9c2d1a4b6e
Revises: j618_foundation
Create Date: 2026-03-22 19:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7f9c2d1a4b6e"
down_revision = "j618_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invitations",
        sa.Column("token", sa.String(length=64), nullable=True),
    )
    op.add_column("invitations", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.execute(
        """
        UPDATE invitations
        SET
            token = md5(id::text || clock_timestamp()::text || random()::text)
                || md5(random()::text || id::text),
            expires_at = COALESCE(expires_at, created_at + interval '48 hours')
        WHERE status = 'pending'
        """
    )
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_column("invitations", "expires_at")
    op.drop_column("invitations", "token")
