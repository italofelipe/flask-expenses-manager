"""PERF-1 — Add missing indexes on tags.user_id and accounts.user_id

These single-column indexes were identified during a production index audit
and applied directly in prod on 2026-04-12.  This migration codifies them
so that all environments (CI, staging, dev) stay in sync.

Hot paths addressed:
  - Tag list: WHERE user_id = ?  (every tag query filters by owner)
  - Account list: WHERE user_id = ?  (every account query filters by owner)

Both use ``if_not_exists=True`` for idempotency — prod already has them.

Revision ID: perf1_tags_accounts
Revises: 831b99cc041f
Create Date: 2026-04-12 21:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "perf1_tags_accounts"
down_revision = "831b99cc041f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_tags_user_id",
        "tags",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_accounts_user_id",
        "accounts",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_user_id", table_name="accounts", if_exists=True)
    op.drop_index("ix_tags_user_id", table_name="tags", if_exists=True)
