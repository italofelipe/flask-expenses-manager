"""HD-1053 — Add optimistic-locking version column to shared_entries

Adds ``version INTEGER NOT NULL DEFAULT 0`` to ``shared_entries``.
Existing rows receive ``version = 0`` via the server_default.

Clients must include the current ``version`` value in mutation requests
(PATCH /shared-entries/{id}).  The update is rejected with HTTP 409
(CONFLICT_CONCURRENT_EDIT) if the version doesn't match the DB value.

Revision ID: hd1053_shared_entries_version
Revises: hd1051_audit_retention_index
Create Date: 2026-04-15 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "hd1053_shared_entries_version"
down_revision = "hd1051_audit_retention_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("shared_entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "version",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("shared_entries") as batch_op:
        batch_op.drop_column("version")
