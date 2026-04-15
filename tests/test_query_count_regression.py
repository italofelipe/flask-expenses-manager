"""Query-count regression gate — CI enforcement for N+1 prevention (#1054).

Each test creates N rows that would produce N extra DB round-trips if eager
loading were removed, then asserts the actual SELECT count is bounded by a
small constant independent of N.

Design: SQLAlchemy engine "before_cursor_execute" event listener (same
pattern as test_portfolio_valuation_eager_load.py).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Iterator
from uuid import uuid4

from sqlalchemy import event

from app.extensions.database import db

# ---------------------------------------------------------------------------
# Helper: query counter
# ---------------------------------------------------------------------------


@contextmanager
def count_selects(engine, *, table: str | None = None) -> Iterator[list[str]]:
    """Context manager that collects SELECT statements fired during its body.

    If ``table`` is provided, only statements whose text contains that table
    name are counted.  Use this to ignore auxiliary queries (e.g. sequences,
    pg_stat) that are irrelevant to the N+1 check.
    """
    captured: list[str] = []

    def _listener(conn, cursor, statement, *_args, **_kwargs):
        upper = statement.strip().upper()
        if not upper.startswith("SELECT"):
            return
        if table is None or table in statement:
            captured.append(statement)

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        yield captured
    finally:
        event.remove(engine, "before_cursor_execute", _listener)


# ---------------------------------------------------------------------------
# Helpers: lightweight model factories
# ---------------------------------------------------------------------------


def _make_user(suffix: str | None = None):
    from app.models.user import User

    s = suffix or uuid4().hex[:6]
    return User(
        id=uuid4(),
        name=f"qc-{s}",
        email=f"qc-{s}@test.com",
        password="hashed",
    )


def _make_transaction(user_id, *, tag_id=None, account_id=None, credit_card_id=None):
    from app.models.transaction import Transaction

    return Transaction(
        id=uuid4(),
        user_id=user_id,
        title="QC txn",
        amount=100,
        type="EXPENSE",
        due_date=date(2026, 6, 1),
        tag_id=tag_id,
        account_id=account_id,
        credit_card_id=credit_card_id,
    )


def _make_tag(user_id):
    from app.models.tag import Tag

    return Tag(id=uuid4(), user_id=user_id, name="Food", color="#ff0000")


def _make_budget(user_id, tag_id):
    from app.models.budget import Budget

    return Budget(
        id=uuid4(),
        user_id=user_id,
        tag_id=tag_id,
        name="QC Budget",
        amount=500,
        period="monthly",
    )


def _make_shared_entry(owner_id, transaction_id):
    from app.models.shared_entry import SharedEntry, SharedEntryStatus, SplitType

    return SharedEntry(
        id=uuid4(),
        owner_id=owner_id,
        transaction_id=transaction_id,
        split_type=SplitType.EQUAL,
        status=SharedEntryStatus.PENDING,
    )


def _make_invitation(shared_entry_id, from_user_id):
    from app.models.shared_entry import Invitation

    return Invitation(
        id=uuid4(),
        shared_entry_id=shared_entry_id,
        from_user_id=from_user_id,
        to_user_email="inv@test.com",
    )


# ---------------------------------------------------------------------------
# 1. Transactions list — no lazy relationship traversal
# ---------------------------------------------------------------------------

N_ITEMS = 3  # number of rows created per test
MAX_SELECTS_TRANSACTIONS = 3  # count + select + optional sequence/ping
MAX_SELECTS_BUDGETS = 2  # 1 JOIN query (joinedload) + leeway for Flask-SQLAlchemy
MAX_SELECTS_SHARED_ENTRIES = 3  # 1 main + 1 batch (selectinload) + leeway


class TestTransactionListQueryCount:
    """Verifies GET /transactions list stays O(1) queries regardless of N."""

    def test_list_active_transactions_bounded_queries(self, app) -> None:
        """get_active_transactions fires at most MAX_SELECTS_TRANSACTIONS SELECTs
        on the 'transactions' table even when N transactions have tag/account FKs.
        """
        from app.application.services.transaction_ledger_service import (
            TransactionLedgerService,
        )

        with app.app_context():
            user = _make_user("txnqc")
            db.session.add(user)
            db.session.flush()

            tag = _make_tag(user.id)
            db.session.add(tag)
            db.session.flush()

            for _ in range(N_ITEMS):
                txn = _make_transaction(user.id, tag_id=tag.id)
                db.session.add(txn)
            db.session.commit()
            db.session.expire_all()

            svc = TransactionLedgerService.with_defaults(user.id)

            with count_selects(db.engine, table="transactions") as selects:
                result = svc.get_active_transactions(
                    page=1,
                    per_page=20,
                    transaction_type=None,
                    status=None,
                    start_date=None,
                    end_date=None,
                    tag_id=None,
                    account_id=None,
                    credit_card_id=None,
                )

            assert result["pagination"]["total"] == N_ITEMS
            n_selects = len(selects)
            assert n_selects <= MAX_SELECTS_TRANSACTIONS, (
                f"Expected ≤{MAX_SELECTS_TRANSACTIONS} SELECT(s) on 'transactions' "
                f"(count + fetch), got {n_selects}. "
                "A lazy relationship traversal inside the serializer would produce "
                f"N+1={N_ITEMS + 1} queries — remove it or add selectinload."
            )

    def test_list_active_transactions_no_tag_relationship_traversal(self, app) -> None:
        """Serializer must NOT access transaction.tag (lazy relationship).

        Accessing transaction.tag would fire one SELECT per item — the query
        count would grow from 2 to 2+N.  This test enforces that only FK
        columns (tag_id) are read, not the related Tag object.
        """
        from app.application.services.transaction_ledger_service import (
            TransactionLedgerService,
        )

        with app.app_context():
            user = _make_user("txnnotagqc")
            db.session.add(user)
            db.session.flush()

            tag = _make_tag(user.id)
            db.session.add(tag)
            db.session.flush()

            for _ in range(N_ITEMS):
                txn = _make_transaction(user.id, tag_id=tag.id)
                db.session.add(txn)
            db.session.commit()
            db.session.expire_all()

            svc = TransactionLedgerService.with_defaults(user.id)

            with count_selects(db.engine, table="tags") as tag_selects:
                svc.get_active_transactions(
                    page=1,
                    per_page=20,
                    transaction_type=None,
                    status=None,
                    start_date=None,
                    end_date=None,
                    tag_id=None,
                    account_id=None,
                    credit_card_id=None,
                )

            # Zero tag SELECTs means serializer never touches transaction.tag
            assert len(tag_selects) == 0, (
                f"Serializer fired {len(tag_selects)} SELECT(s) on 'tags' — "
                "this means transaction.tag is being accessed lazily (N+1). "
                "Use tag_id (FK column) instead of transaction.tag."
            )


# ---------------------------------------------------------------------------
# 2. Budgets list — joinedload(Budget.tag) must prevent N extra tag queries
# ---------------------------------------------------------------------------


class TestBudgetListQueryCount:
    """Verifies list_budgets stays O(1) queries via joinedload."""

    def test_list_budgets_bounded_queries(self, app) -> None:
        """list_budgets fires at most MAX_SELECTS_BUDGETS SELECTs even for N
        budgets each referencing a Tag.
        """
        from app.services.budget_service import BudgetService

        with app.app_context():
            user = _make_user("budqc")
            db.session.add(user)
            db.session.flush()

            for _ in range(N_ITEMS):
                tag = _make_tag(user.id)
                db.session.add(tag)
                db.session.flush()
                budget = _make_budget(user.id, tag.id)
                db.session.add(budget)
            db.session.commit()
            db.session.expire_all()

            svc = BudgetService(user.id)

            with count_selects(db.engine, table="budgets") as bud_selects:
                budgets = svc.list_budgets(active_only=False)

            assert len(budgets) == N_ITEMS
            n_selects = len(bud_selects)
            assert n_selects <= MAX_SELECTS_BUDGETS, (
                f"Expected ≤{MAX_SELECTS_BUDGETS} SELECT(s) on 'budgets' "
                f"(joinedload), got {n_selects}. "
                "Removing joinedload(Budget.tag) would make this N+1."
            )

    def test_list_budgets_no_per_item_tag_query(self, app) -> None:
        """With joinedload, tags are fetched via JOIN — not N separate queries."""
        from app.services.budget_service import BudgetService

        with app.app_context():
            user = _make_user("budnotagqc")
            db.session.add(user)
            db.session.flush()

            tags = []
            for _ in range(N_ITEMS):
                tag = _make_tag(user.id)
                db.session.add(tag)
                db.session.flush()
                budget = _make_budget(user.id, tag.id)
                db.session.add(budget)
                tags.append(tag)
            db.session.commit()
            db.session.expire_all()

            svc = BudgetService(user.id)

            with count_selects(db.engine, table="tags") as tag_selects:
                budgets = svc.list_budgets(active_only=False)
                # Force access of budget.tag.name to trigger any lazy queries
                _ = [b.tag.name if b.tag else None for b in budgets]

            # joinedload embeds tags as a LEFT OUTER JOIN in the main query.
            # That produces exactly 1 SELECT containing 'tags' — not N separate
            # per-item queries. N+1 would produce 1 + N_ITEMS queries.
            assert len(tag_selects) == 1, (
                f"Expected exactly 1 SELECT containing 'tags' (the JOIN), "
                f"got {len(tag_selects)}. "
                f"N+1 would produce {1 + N_ITEMS} queries — "
                "ensure joinedload(Budget.tag) is in place."
            )


# ---------------------------------------------------------------------------
# 3. SharedEntries list — selectinload(SharedEntry.invitations)
# ---------------------------------------------------------------------------


class TestSharedEntriesListQueryCount:
    """Verifies list_shared_by_me fires at most 2 queries via selectinload."""

    def test_list_shared_by_me_bounded_queries(self, app) -> None:
        """list_shared_by_me fires exactly 2 SELECTs for N shared entries
        (1 for shared_entries, 1 batch for all invitations).
        """
        from app.services.shared_entry_service import list_shared_by_me

        with app.app_context():
            user = _make_user("seqc")
            db.session.add(user)
            db.session.flush()

            for _ in range(N_ITEMS):
                txn = _make_transaction(user.id)
                db.session.add(txn)
                db.session.flush()
                se = _make_shared_entry(user.id, txn.id)
                db.session.add(se)
                db.session.flush()
                inv = _make_invitation(se.id, user.id)
                db.session.add(inv)
            db.session.commit()
            db.session.expire_all()

            with count_selects(db.engine) as selects:
                entries = list_shared_by_me(owner_id=user.id)
                # Force access of .invitations on every entry
                for entry in entries:
                    _ = list(entry.invitations)

            assert len(entries) == N_ITEMS
            # With selectinload: 1 query for shared_entries + 1 batch for invitations
            # + potential 1 for transactions (lazy="joined" on SharedEntry.transaction)
            assert len(selects) <= MAX_SELECTS_SHARED_ENTRIES, (
                f"Expected ≤{MAX_SELECTS_SHARED_ENTRIES} SELECTs for "
                f"{N_ITEMS} entries+invitations, got {len(selects)}. "
                "Removing selectinload(SharedEntry.invitations) would produce "
                f"N+1={N_ITEMS + 1} invitation queries."
            )

    def test_list_shared_by_me_no_per_item_invitation_query(self, app) -> None:
        """selectinload must prevent separate per-item invitation queries."""
        from app.services.shared_entry_service import list_shared_by_me

        with app.app_context():
            user = _make_user("senoinvqc")
            db.session.add(user)
            db.session.flush()

            for _ in range(N_ITEMS):
                txn = _make_transaction(user.id)
                db.session.add(txn)
                db.session.flush()
                se = _make_shared_entry(user.id, txn.id)
                db.session.add(se)
                db.session.flush()
                inv = _make_invitation(se.id, user.id)
                db.session.add(inv)
            db.session.commit()
            db.session.expire_all()

            with count_selects(db.engine, table="invitations") as inv_selects:
                entries = list_shared_by_me(owner_id=user.id)
                _ = [list(e.invitations) for e in entries]

            # selectinload fires exactly 1 batch SELECT for invitations
            assert len(inv_selects) == 1, (
                f"Expected exactly 1 batch SELECT for invitations (selectinload), "
                f"got {len(inv_selects)}. "
                "N+1 would produce {N_ITEMS} separate queries."
            )
