"""HD-1051 — Add BRIN index on audit_events.created_at for retention purge

``ix_audit_events_created_at`` (btree) already exists for random-access lookups
by request_id join.  The retention job deletes all rows older than a configurable
cutoff, which is a sequential-scan-friendly range query on an append-only table.
A BRIN index is a far better fit: it is orders-of-magnitude smaller than a btree
and exploits the physical correlation between insertion order and created_at.

The migration is idempotent — it uses IF NOT EXISTS so running it twice is safe.

Revision ID: hd1051_audit_retention_index
Revises: h1028_refresh_tokens
Create Date: 2026-04-15 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "hd1051_audit_retention_index"
down_revision = "h1028_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_events_created_at_brin",
        "audit_events",
        ["created_at"],
        postgresql_using="brin",
        postgresql_with={"pages_per_range": "128"},
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_events_created_at_brin",
        table_name="audit_events",
        if_exists=True,
    )
