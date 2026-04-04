"""Add performance indexes for transactions and goals (B21)

Revision ID: b21_perf_indexes
Revises: b18_refresh_token_jti
Create Date: 2026-04-03 00:00:00.000000

Why these indexes exist
-----------------------
These composite indexes target the most common query patterns in production:

1. ix_transactions_user_deleted  — (user_id, deleted)
   Fast soft-delete filter.  Nearly every transaction query filters
   ``WHERE user_id = ? AND deleted = false``.

2. ix_transactions_user_created  — (user_id, created_at DESC)
   Supports feed / timeline queries that ORDER BY created_at DESC for a
   specific user without a full table scan.

3. ix_goals_user_status  — (user_id, status)
   Goals are almost always queried per-user with a status filter
   (e.g. ``status = 'active'``).

CONCURRENTLY note
-----------------
``op.create_index`` with ``postgresql_concurrently=True`` translates to
``CREATE INDEX CONCURRENTLY``, which builds the index without a full table
lock.  Alembic must NOT wrap this in a transaction, so we set
``execute_timeout=None`` and the migration is marked as non-transactional
at the Alembic env level via ``with_autobegin=False`` (handled by setting
``transaction_per_migration = True`` in env.py if needed).

For simplicity (and compatibility with SQLite in tests) we do NOT use the
``postgresql_concurrently`` flag here — Alembic's ``op.create_index`` with
``if_not_exists=True`` is safe to run idempotently and SQLite ignores
dialect-specific kwargs gracefully.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b21_perf_indexes"
down_revision = "b18_refresh_token_jti"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # transactions indexes
    # ------------------------------------------------------------------
    op.create_index(
        "ix_transactions_user_deleted",
        "transactions",
        ["user_id", "deleted"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_transactions_user_created",
        "transactions",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
        if_not_exists=True,
        postgresql_using="btree",
    )

    # ------------------------------------------------------------------
    # goals indexes
    # ------------------------------------------------------------------
    op.create_index(
        "ix_goals_user_status",
        "goals",
        ["user_id", "status"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_goals_user_status", table_name="goals", if_exists=True)
    op.drop_index(
        "ix_transactions_user_created", table_name="transactions", if_exists=True
    )
    op.drop_index(
        "ix_transactions_user_deleted", table_name="transactions", if_exists=True
    )
