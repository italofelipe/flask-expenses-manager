"""PERF-2 — N+1 query count regression tests.

Instruments SQLAlchemy query execution and asserts that list endpoints
stay within a bounded number of queries, regardless of row count.

The goal: listing N rows must NOT produce O(N) queries.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import Generator

from sqlalchemy import event

from app.extensions.database import db
from app.models.account import Account
from app.models.budget import Budget
from app.models.tag import Tag
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.models.wallet import Wallet


@contextmanager
def count_queries() -> Generator[list[str], None, None]:
    """Context manager that collects all SQL statements executed."""
    queries: list[str] = []
    engine = db.engine

    def _receive(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _receive)
    try:
        yield queries
    finally:
        event.remove(engine, "before_cursor_execute", _receive)


def _create_user(app) -> User:  # type: ignore[no-untyped-def]
    user = User(
        id=uuid.uuid4(),
        name="PERF-2 Test User",
        email=f"perf2-{uuid.uuid4().hex[:8]}@test.com",
        password="hash",
    )
    db.session.add(user)
    db.session.flush()
    return user


def _create_tag(user: User) -> Tag:
    tag = Tag(user_id=user.id, name=f"Tag-{uuid.uuid4().hex[:6]}", color="#FF0000")
    db.session.add(tag)
    db.session.flush()
    return tag


def _create_account(user: User) -> Account:
    account = Account(
        user_id=user.id,
        name=f"Account-{uuid.uuid4().hex[:6]}",
        initial_balance=Decimal("1000.00"),
    )
    db.session.add(account)
    db.session.flush()
    return account


# -----------------------------------------------------------------------
# Transactions list — must NOT produce N+1 on tag/account/credit_card
# -----------------------------------------------------------------------


def test_transaction_list_query_count_bounded(app) -> None:
    """Listing 20 transactions must use ≤ 10 queries (not 1 + 3*N)."""
    from app.application.services.transaction_ledger_service import (
        TransactionLedgerService,
    )

    with app.app_context():
        user = _create_user(app)
        tag = _create_tag(user)
        account = _create_account(user)

        for i in range(20):
            tx = Transaction(
                user_id=user.id,
                title=f"TX-{i}",
                amount=Decimal("50.00"),
                type=TransactionType.EXPENSE,
                status=TransactionStatus.PENDING,
                due_date=date.today() + timedelta(days=i),
                tag_id=tag.id,
                account_id=account.id,
            )
            db.session.add(tx)
        db.session.commit()

        service = TransactionLedgerService.with_defaults(user_id=user.id)

        with count_queries() as queries:
            result = service.get_active_transactions(
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

        assert len(result["items"]) == 20
        # 2 queries expected: COUNT + SELECT with LIMIT/OFFSET
        # If N+1 existed, we'd see 20*3 = 60+ extra queries
        assert len(queries) <= 10, (
            f"Transaction list produced {len(queries)} queries for 20 rows — "
            f"suspected N+1. Queries: {queries[:15]}"
        )


def test_transaction_due_range_query_count_bounded(app) -> None:
    """Due-range query must use ≤ 10 queries for 20 transactions."""
    from app.application.services.transaction_ledger_service import (
        TransactionLedgerService,
    )

    with app.app_context():
        user = _create_user(app)
        tag = _create_tag(user)

        today = date.today()
        for i in range(20):
            tx = Transaction(
                user_id=user.id,
                title=f"Due-{i}",
                amount=Decimal("30.00"),
                type=TransactionType.EXPENSE,
                status=TransactionStatus.PENDING,
                due_date=today + timedelta(days=i),
                tag_id=tag.id,
            )
            db.session.add(tx)
        db.session.commit()

        service = TransactionLedgerService.with_defaults(user_id=user.id)

        with count_queries() as queries:
            result = service.get_due_transactions(
                start_date=today,
                end_date=today + timedelta(days=30),
                page=1,
                per_page=20,
            )

        assert len(result["items"]) == 20
        assert len(queries) <= 10, (
            f"Due-range list produced {len(queries)} queries for 20 rows — "
            f"suspected N+1. Queries: {queries[:15]}"
        )


# -----------------------------------------------------------------------
# Budget list — already has joinedload(Budget.tag)
# -----------------------------------------------------------------------


def test_budget_list_query_count_bounded(app) -> None:
    """Budget list with joinedload must use ≤ 5 queries for 10 budgets."""
    from app.services.budget_service import BudgetService

    with app.app_context():
        user = _create_user(app)

        for i in range(10):
            tag = _create_tag(user)
            budget = Budget(
                user_id=user.id,
                tag_id=tag.id,
                name=f"Budget-{i}",
                amount=Decimal("500.00"),
            )
            db.session.add(budget)
        db.session.commit()

        service = BudgetService(user_id=user.id)

        with count_queries() as queries:
            result = service.list_budgets()

        assert len(result) >= 10
        assert len(queries) <= 5, (
            f"Budget list produced {len(queries)} queries for 10 rows — "
            f"suspected N+1 on tag relationship. Queries: {queries[:10]}"
        )


# -----------------------------------------------------------------------
# Wallet list — no relationships accessed during serialization
# -----------------------------------------------------------------------


def test_wallet_list_query_count_bounded(app) -> None:
    """Wallet list must use ≤ 5 queries for 10 entries."""
    from app.application.services.wallet_application_service import (
        WalletApplicationService,
    )

    with app.app_context():
        user = _create_user(app)

        for i in range(10):
            wallet = Wallet(
                user_id=user.id,
                name=f"Asset-{i}",
                ticker=f"TST{i}",
                quantity=100,
                register_date=date.today(),
                should_be_on_wallet=True,
            )
            db.session.add(wallet)
        db.session.commit()

        service = WalletApplicationService.with_defaults(user_id=user.id)

        with count_queries() as queries:
            result = service.list_entries(page=1, per_page=10)

        assert len(result["items"]) == 10
        assert len(queries) <= 5, (
            f"Wallet list produced {len(queries)} queries for 10 rows — "
            f"suspected N+1. Queries: {queries[:10]}"
        )
