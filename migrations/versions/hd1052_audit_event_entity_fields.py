"""HD-1052 — Add entity-level audit fields to audit_events

Adds nullable columns for recording soft-delete operations at the entity
level (not just the HTTP request level):
  - entity_type  — e.g. "transaction", "user"
  - entity_id    — UUID of the deleted entity as text
  - action       — e.g. "soft_delete"
  - actor_id     — UUID of the authenticated user who performed the action
  - extra        — JSON blob with reason, metadata, etc.

Existing HTTP-level audit rows are unaffected (all new columns are nullable).
Composite index on (entity_type, entity_id) supports the
``GET /admin/audit-trail/{entity_type}/{entity_id}`` query.

Revision ID: hd1052_audit_entity_fields
Revises: h1028_refresh_tokens
Create Date: 2026-04-15 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "hd1052_audit_entity_fields"
down_revision = "h1028_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(sa.Column("entity_type", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("entity_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("action", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("actor_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("extra", sa.Text, nullable=True))

    op.create_index(
        "ix_audit_events_entity",
        "audit_events",
        ["entity_type", "entity_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_entity", table_name="audit_events", if_exists=True)

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_column("extra")
        batch_op.drop_column("actor_id")
        batch_op.drop_column("action")
        batch_op.drop_column("entity_id")
        batch_op.drop_column("entity_type")
