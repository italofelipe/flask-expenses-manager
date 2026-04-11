"""perf_gap_01_performance_indexes

PERF-GAP-01 — Add composite indexes on hot query paths to eliminate
full-table scans for per-user filters on transactions, goals, and wallets.

Hot paths addressed:
  - Transaction list: WHERE user_id = ? AND deleted = false
  - Transaction date range: WHERE user_id = ? AND deleted = false AND due_date BETWEEN ? AND ?
  - Goal list with status: WHERE user_id = ? AND status = ?
  - Goal ordering: ORDER BY priority ASC, created_at DESC
  - Wallet list: WHERE user_id = ?
  - Wallet goal projection: WHERE user_id = ? AND should_be_on_wallet = true

Revision ID: 831b99cc041f
Revises: p916_webhook_events
Create Date: 2026-04-10 21:37:30.030213

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "831b99cc041f"
down_revision = "p916_webhook_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Transactions — all list queries filter on (user_id, deleted)
    # The due_date suffix serves the date-range filter and monthly aggregates.
    # -----------------------------------------------------------------------
    op.create_index(
        "ix_transactions_user_deleted",
        "transactions",
        ["user_id", "deleted"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_user_deleted_due_date",
        "transactions",
        ["user_id", "deleted", "due_date"],
        unique=False,
    )

    # -----------------------------------------------------------------------
    # Goals — list filtered by (user_id, status); ordering uses priority +
    # created_at so a covering index avoids a sort step.
    # -----------------------------------------------------------------------
    op.create_index(
        "ix_goals_user_status",
        "goals",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_goals_user_priority_created_at",
        "goals",
        ["user_id", "priority", "created_at"],
        unique=False,
    )

    # -----------------------------------------------------------------------
    # Wallets — all portfolio/goal-projection queries filter by user_id;
    # secondary index for should_be_on_wallet boolean filter.
    # -----------------------------------------------------------------------
    op.create_index(
        "ix_wallets_user_id",
        "wallets",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_wallets_user_should_be_on_wallet",
        "wallets",
        ["user_id", "should_be_on_wallet"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_wallets_user_should_be_on_wallet", table_name="wallets")
    op.drop_index("ix_wallets_user_id", table_name="wallets")
    op.drop_index("ix_goals_user_priority_created_at", table_name="goals")
    op.drop_index("ix_goals_user_status", table_name="goals")
    op.drop_index("ix_transactions_user_deleted_due_date", table_name="transactions")
    op.drop_index("ix_transactions_user_deleted", table_name="transactions")
