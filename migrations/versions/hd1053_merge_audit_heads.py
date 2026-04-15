"""Merge hd1051 + hd1052 into a single head.

hd1051 (BRIN index) and hd1052 (entity fields) were both branched off
h1028_refresh_tokens independently.  This merge migration linearises
the chain so alembic sees a single head again.

Revision ID: hd1053_merge_audit_heads
Revises: hd1051_audit_retention_index, hd1052_audit_entity_fields
Create Date: 2026-04-15 01:00:00.000000

"""

from __future__ import annotations

revision = "hd1053_merge_audit_heads"
down_revision = ("hd1051_audit_retention_index", "hd1052_audit_entity_fields")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
