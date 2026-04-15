"""Merge hd1053_merge_audit_heads and hd1053_shared_entries_version.

Both migrations branch from hd1051_audit_retention_index independently.
This merge migration linearises the chain so alembic sees a single head.

Revision ID: hd1054_merge_1053_heads
Revises: hd1053_merge_audit_heads, hd1053_shared_entries_version
Create Date: 2026-04-15

"""

from __future__ import annotations

revision = "hd1054_merge_1053_heads"
down_revision = ("hd1053_merge_audit_heads", "hd1053_shared_entries_version")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
