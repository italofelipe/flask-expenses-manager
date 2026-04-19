"""API-level query count assertions (#1054).

Verifies that list endpoints stay within a bounded SQL query count when
fetching N rows — i.e., they do NOT exhibit N+1 behaviour.

The ``query_counter`` fixture (defined in tests/conftest.py) counts every
SQL statement fired against the SQLAlchemy engine.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.extensions.database import db
from app.models.account import Account
from app.models.goal import Goal
from app.models.tag import Tag
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user() -> User:
    user = User(
        id=uuid.uuid4(),
        name="QC Test User",
        email=f"qc-{uuid.uuid4().hex[:8]}@test.com",
        password="hash",
    )
    db.session.add(user)
    db.session.flush()
    return user


def _make_tag(user: User) -> Tag:
    tag = Tag(user_id=user.id, name=f"Tag-{uuid.uuid4().hex[:6]}", color="#AABBCC")
    db.session.add(tag)
    db.session.flush()
    return tag


def _make_account(user: User) -> Account:
    account = Account(
        user_id=user.id,
        name=f"Acc-{uuid.uuid4().hex[:6]}",
        initial_balance=Decimal("100.00"),
    )
    db.session.add(account)
    db.session.flush()
    return account


# ---------------------------------------------------------------------------
# Transaction list — selectinload on tag / account / credit_card
# ---------------------------------------------------------------------------


def test_transaction_list_bounded_queries(
    app: object, query_counter: dict[str, int]
) -> None:
    """Transaction list for 10 rows must fire ≤ 5 queries (not 1+3*N)."""
    from app.application.services.transaction_ledger_service import (
        TransactionLedgerService,
    )

    with app.app_context():  # type: ignore[union-attr]
        user = _make_user()
        tag = _make_tag(user)
        account = _make_account(user)

        for i in range(10):
            tx = Transaction(
                user_id=user.id,
                title=f"Tx-{i}",
                amount=Decimal("25.00"),
                type=TransactionType.EXPENSE,
                status=TransactionStatus.PENDING,
                due_date=date.today() + timedelta(days=i),
                tag_id=tag.id,
                account_id=account.id,
            )
            db.session.add(tx)
        db.session.commit()

        service = TransactionLedgerService.with_defaults(user_id=user.id)

        # Reset counter AFTER setup so only the service call counts.
        query_counter["n"] = 0

        result = service.get_active_transactions(
            page=1,
            per_page=10,
            transaction_type=None,
            status=None,
            start_date=None,
            end_date=None,
            tag_id=None,
            account_id=None,
            credit_card_id=None,
        )

    assert len(result["items"]) == 10, "Expected 10 transaction items in result"
    assert query_counter["n"] <= 5, (
        f"Transaction list issued {query_counter['n']} queries for 10 rows — "
        "suspected N+1.  Expected ≤ 5 (COUNT + main SELECT + up to 3 selectinloads)."
    )


# ---------------------------------------------------------------------------
# Goals list — no lazy relationships, should be ≤ 2 queries
# ---------------------------------------------------------------------------


def test_goal_list_bounded_queries(app: object, query_counter: dict[str, int]) -> None:
    """Goal list for 10 rows must fire ≤ 5 queries (Goal has no lazy relations)."""
    from app.services.goal_service import GoalService

    with app.app_context():  # type: ignore[union-attr]
        user = _make_user()

        for i in range(10):
            goal = Goal(
                user_id=user.id,
                title=f"Goal-{i}",
                target_amount=Decimal("1000.00"),
                current_amount=Decimal("0.00"),
                priority=3,
                status="active",
            )
            db.session.add(goal)
        db.session.commit()

        service = GoalService(user_id=user.id)

        query_counter["n"] = 0

        goals, pagination = service.list_goals(page=1, per_page=10)

    assert len(goals) == 10, "Expected 10 goals in result"
    assert pagination["total"] >= 10
    assert query_counter["n"] <= 5, (
        f"Goal list issued {query_counter['n']} queries for 10 rows — "
        "expected ≤ 5 (SELECT + optional COUNT)."
    )
