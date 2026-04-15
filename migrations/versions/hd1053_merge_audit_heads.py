"""Merge hd1051 and hd1052 audit migration heads.

Revision ID: hd1053_merge_audit_heads
Revises: hd1051_audit_retention_index, hd1052_audit_entity_fields
Create Date: 2026-04-15

"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "hd1053_merge_audit_heads"
down_revision = ("hd1051_audit_retention_index", "hd1052_audit_entity_fields")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
