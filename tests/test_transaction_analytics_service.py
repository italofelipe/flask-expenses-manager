"""REF-GAP-03 — Isolated unit tests for TransactionAnalyticsService.

Verifies aggregations, status counts, paginated queries, and top-category
rankings produced by TransactionAnalyticsService in isolation from the
application facade.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions.database import db
from app.models.tag import Tag
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.transaction_analytics_service import TransactionAnalyticsService


@pytest.fixture()
def user_id():
    return uuid4()


@pytest.fixture()
def analytics(user_id):
    return TransactionAnalyticsService(user_id)


def _make_transaction(
    user_id,
    *,
    title: str = "Tx",
    amount: str = "100.00",
    tx_type: TransactionType = TransactionType.EXPENSE,
    status: TransactionStatus = TransactionStatus.PAID,
    year: int = 2030,
    month: int = 6,
    day: int = 1,
    tag_id=None,
) -> Transaction:
    from datetime import date

    return Transaction(
        user_id=user_id,
        title=title,
        amount=Decimal(amount),
        type=tx_type,
        status=status,
        due_date=date(year, month, day),
        tag_id=tag_id,
    )


class TestGetMonthAggregates:
    def test_empty_month_returns_zeros(self, app, analytics, user_id) -> None:
        with app.app_context():
            result = analytics.get_month_aggregates(year=2030, month_number=1)

        assert result["income_total"] == 0
        assert result["expense_total"] == 0
        assert result["balance"] == 0
        assert result["total_transactions"] == 0
        assert result["income_transactions"] == 0
        assert result["expense_transactions"] == 0

    def test_income_and_expense_aggregated_correctly(
        self, app, analytics, user_id
    ) -> None:
        with app.app_context():
            db.session.add(
                _make_transaction(
                    user_id,
                    title="Salary",
                    amount="3000.00",
                    tx_type=TransactionType.INCOME,
                )
            )
            db.session.add(
                _make_transaction(
                    user_id,
                    title="Rent",
                    amount="1200.00",
                    tx_type=TransactionType.EXPENSE,
                )
            )
            db.session.add(
                _make_transaction(
                    user_id,
                    title="Groceries",
                    amount="400.00",
                    tx_type=TransactionType.EXPENSE,
                )
            )
            db.session.commit()

            result = analytics.get_month_aggregates(year=2030, month_number=6)

        assert float(result["income_total"]) == pytest.approx(3000.00)
        assert float(result["expense_total"]) == pytest.approx(1600.00)
        assert float(result["balance"]) == pytest.approx(1400.00)
        assert result["total_transactions"] == 3
        assert result["income_transactions"] == 1
        assert result["expense_transactions"] == 2

    def test_deleted_transactions_are_excluded(self, app, analytics, user_id) -> None:
        with app.app_context():
            tx = _make_transaction(user_id, amount="500.00")
            tx.deleted = True
            db.session.add(tx)
            db.session.commit()

            result = analytics.get_month_aggregates(year=2030, month_number=6)

        assert result["total_transactions"] == 0
        assert result["expense_total"] == 0

    def test_transactions_from_other_users_are_excluded(
        self, app, analytics, user_id
    ) -> None:
        other_user_id = uuid4()
        with app.app_context():
            db.session.add(
                _make_transaction(other_user_id, title="Other income", amount="9999.00")
            )
            db.session.commit()

            result = analytics.get_month_aggregates(year=2030, month_number=6)

        assert result["total_transactions"] == 0

    def test_transactions_in_different_month_excluded(
        self, app, analytics, user_id
    ) -> None:
        with app.app_context():
            db.session.add(_make_transaction(user_id, amount="200.00", month=5))
            db.session.commit()

            result = analytics.get_month_aggregates(year=2030, month_number=6)

        assert result["total_transactions"] == 0


class TestGetStatusCounts:
    def test_empty_returns_all_zeros(self, app, analytics, user_id) -> None:
        with app.app_context():
            counts = analytics.get_status_counts(year=2030, month_number=6)

        assert counts == {
            "paid": 0,
            "pending": 0,
            "cancelled": 0,
            "postponed": 0,
            "overdue": 0,
        }

    def test_counts_per_status(self, app, analytics, user_id) -> None:
        with app.app_context():
            db.session.add(
                _make_transaction(user_id, title="P1", status=TransactionStatus.PAID)
            )
            db.session.add(
                _make_transaction(user_id, title="P2", status=TransactionStatus.PAID)
            )
            db.session.add(
                _make_transaction(user_id, title="N1", status=TransactionStatus.PENDING)
            )
            db.session.commit()

            counts = analytics.get_status_counts(year=2030, month_number=6)

        assert counts["paid"] == 2
        assert counts["pending"] == 1
        assert counts["cancelled"] == 0


class TestGetMonthTransactions:
    def test_returns_transactions_for_month(self, app, analytics, user_id) -> None:
        with app.app_context():
            db.session.add(_make_transaction(user_id, title="June tx", month=6))
            db.session.add(_make_transaction(user_id, title="July tx", month=7))
            db.session.commit()

            txns = analytics.get_month_transactions(year=2030, month_number=6)

        assert len(txns) == 1
        assert txns[0].title == "June tx"

    def test_count_matches_list_length(self, app, analytics, user_id) -> None:
        with app.app_context():
            for i in range(5):
                db.session.add(_make_transaction(user_id, title=f"Tx {i}", day=i + 1))
            db.session.commit()

            count = analytics.get_month_transaction_count(year=2030, month_number=6)
            txns = analytics.get_month_transactions(year=2030, month_number=6)

        assert count == 5
        assert len(txns) == 5


class TestGetMonthTransactionsPage:
    def test_pagination_returns_correct_slice(self, app, analytics, user_id) -> None:
        with app.app_context():
            for i in range(10):
                db.session.add(
                    _make_transaction(user_id, title=f"Tx {i:02d}", day=(i % 28) + 1)
                )
            db.session.commit()

            page1 = analytics.get_month_transactions_page(
                year=2030, month_number=6, page=1, per_page=4
            )
            page2 = analytics.get_month_transactions_page(
                year=2030, month_number=6, page=2, per_page=4
            )
            page3 = analytics.get_month_transactions_page(
                year=2030, month_number=6, page=3, per_page=4
            )

        assert len(page1) == 4
        assert len(page2) == 4
        assert len(page3) == 2  # 10 total, 4+4+2


class TestGetTopCategories:
    def test_returns_top_5_by_amount(self, app, analytics, user_id) -> None:
        with app.app_context():
            for i in range(7):
                tag = Tag(user_id=user_id, name=f"Cat {i}")
                db.session.add(tag)
                db.session.flush()
                db.session.add(
                    _make_transaction(
                        user_id,
                        title=f"Expense {i}",
                        amount=str(100 * (i + 1)),
                        tag_id=tag.id,
                    )
                )
            db.session.commit()

            top = analytics.get_top_categories(
                year=2030,
                month_number=6,
                transaction_type=TransactionType.EXPENSE,
            )

        assert len(top) == 5
        # Should be ordered by descending amount
        amounts = [item["total_amount"] for item in top]
        assert amounts == sorted(amounts, reverse=True)

    def test_returns_correct_structure(self, app, analytics, user_id) -> None:
        with app.app_context():
            db.session.add(
                _make_transaction(user_id, title="No category", amount="50.00")
            )
            db.session.commit()

            top = analytics.get_top_categories(
                year=2030,
                month_number=6,
                transaction_type=TransactionType.EXPENSE,
            )

        assert len(top) == 1
        item = top[0]
        assert "tag_id" in item
        assert "category_name" in item
        assert "total_amount" in item
        assert "transactions_count" in item
        assert item["category_name"] == "Sem categoria"
        assert item["tag_id"] is None
