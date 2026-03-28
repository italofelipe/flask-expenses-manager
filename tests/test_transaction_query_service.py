from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from app.application.services.transaction_application_service import (
    TransactionApplicationService,
)
from app.application.services.transaction_query_service import (
    TransactionQueryDependencies,
    TransactionQueryService,
)
from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.transaction_analytics_service import TransactionAnalyticsService


def _build_transaction(
    *,
    user_id: UUID,
    title: str,
    amount: str,
    transaction_type: TransactionType,
    due_date: date,
    created_at: datetime | None = None,
) -> Transaction:
    transaction = Transaction(
        id=uuid4(),
        user_id=user_id,
        title=title,
        amount=Decimal(amount),
        type=transaction_type,
        status=TransactionStatus.PENDING,
        due_date=due_date,
        currency="BRL",
        source="manual",
    )
    if created_at is not None:
        transaction.created_at = created_at
    return transaction


def test_month_summary_prefers_paginated_analytics_path() -> None:
    user_id = uuid4()
    paged_transactions = [
        _build_transaction(
            user_id=user_id,
            title="Conta 1",
            amount="10.00",
            transaction_type=TransactionType.EXPENSE,
            due_date=date(2026, 3, 1),
        ),
        _build_transaction(
            user_id=user_id,
            title="Conta 2",
            amount="20.00",
            transaction_type=TransactionType.EXPENSE,
            due_date=date(2026, 3, 2),
        ),
    ]

    class _PaginatedAnalyticsService(TransactionAnalyticsService):
        def __init__(self, _user_id: UUID) -> None:
            pass

        def get_month_transaction_count(self, **_kwargs: object) -> int:
            return 3

        def get_month_transactions_page(self, **_kwargs: object) -> list[Transaction]:
            return paged_transactions

        def get_month_transactions(self, **_kwargs: object) -> list[Transaction]:
            raise AssertionError("Legacy month transactions path should not be used.")

        def get_month_aggregates(self, **_kwargs: object) -> dict[str, object]:
            return {
                "income_total": Decimal("0.00"),
                "expense_total": Decimal("30.00"),
                "balance": Decimal("-30.00"),
                "total_transactions": 3,
                "income_transactions": 0,
                "expense_transactions": 3,
            }

    service = TransactionApplicationService(
        user_id=user_id,
        analytics_service_factory=_PaginatedAnalyticsService,
    )

    result = service.get_month_summary(month="2026-03", page=1, page_size=2)

    assert result["month"] == "2026-03"
    assert result["expense_total"] == 30.0
    assert result["paginated"]["total"] == 3
    assert result["paginated"]["page_size"] == 2
    assert result["paginated"]["has_next_page"] is True
    assert [item["title"] for item in result["paginated"]["data"]] == [
        "Conta 1",
        "Conta 2",
    ]


def test_month_summary_falls_back_to_legacy_list() -> None:
    user_id = uuid4()
    all_transactions = [
        _build_transaction(
            user_id=user_id,
            title="Conta 1",
            amount="10.00",
            transaction_type=TransactionType.EXPENSE,
            due_date=date(2026, 3, 1),
        ),
        _build_transaction(
            user_id=user_id,
            title="Conta 2",
            amount="20.00",
            transaction_type=TransactionType.EXPENSE,
            due_date=date(2026, 3, 2),
        ),
        _build_transaction(
            user_id=user_id,
            title="Conta 3",
            amount="30.00",
            transaction_type=TransactionType.EXPENSE,
            due_date=date(2026, 3, 3),
        ),
    ]

    class _LegacyAnalyticsService(TransactionAnalyticsService):
        def __init__(self, _user_id: UUID) -> None:
            pass

        def get_month_transactions(self, **_kwargs: object) -> list[Transaction]:
            return all_transactions

        def get_month_aggregates(self, **_kwargs: object) -> dict[str, object]:
            return {
                "income_total": Decimal("0.00"),
                "expense_total": Decimal("60.00"),
                "balance": Decimal("-60.00"),
                "total_transactions": 3,
                "income_transactions": 0,
                "expense_transactions": 3,
            }

    service = TransactionApplicationService(
        user_id=user_id,
        analytics_service_factory=_LegacyAnalyticsService,
    )

    result = service.get_month_summary(month="2026-03", page=2, page_size=2)

    assert result["paginated"]["total"] == 3
    assert result["paginated"]["page"] == 2
    assert result["paginated"]["page_size"] == 2
    assert result["paginated"]["has_next_page"] is False
    assert [item["title"] for item in result["paginated"]["data"]] == ["Conta 3"]


def test_transaction_query_service_expense_period_serializes_without_detail_fetch(
    app: Any,
) -> None:
    with app.app_context():
        user = User(
            name="query-user",
            email="query-user@email.com",
            password="hash",
        )
        db.session.add(user)
        db.session.commit()

        db.session.add_all(
            [
                _build_transaction(
                    user_id=user.id,
                    title="Conta de internet",
                    amount="120.00",
                    transaction_type=TransactionType.EXPENSE,
                    due_date=date(2026, 3, 10),
                    created_at=datetime(2026, 3, 1, 10, 0, 0),
                ),
                _build_transaction(
                    user_id=user.id,
                    title="Salário",
                    amount="2000.00",
                    transaction_type=TransactionType.INCOME,
                    due_date=date(2026, 3, 5),
                    created_at=datetime(2026, 3, 1, 9, 0, 0),
                ),
            ]
        )
        db.session.commit()

        class _FailingApplicationService:
            def get_transaction(self, _transaction_id: UUID) -> dict[str, object]:
                raise AssertionError(
                    "Expense period should not fetch transaction details one by one."
                )

        query_service = TransactionQueryService(
            user_id=user.id,
            dependencies=TransactionQueryDependencies(
                transaction_application_service_factory=lambda _user_id: cast(
                    TransactionApplicationService,
                    _FailingApplicationService(),
                ),
                analytics_service_factory=lambda _user_id: cast(
                    TransactionAnalyticsService,
                    object(),
                ),
            ),
        )

        result = query_service.get_expense_period(
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            page=1,
            per_page=10,
            ordering_clause=Transaction.created_at.asc(),
        )

        assert result["counts"]["total_transactions"] == 2
        assert result["counts"]["income_transactions"] == 1
        assert result["counts"]["expense_transactions"] == 1
        assert result["pagination"]["total"] == 1
        assert [item["title"] for item in result["expenses"]] == ["Conta de internet"]
