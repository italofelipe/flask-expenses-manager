from datetime import date
from decimal import Decimal

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.recurrence_service import RecurrenceService


def _create_user() -> User:
    user = User(name="rec-user", email="rec-user@email.com", password="x")
    db.session.add(user)
    db.session.commit()
    return user


def test_generate_missing_occurrences_is_idempotent(app) -> None:
    with app.app_context():
        user = _create_user()
        template = Transaction(
            user_id=user.id,
            title="Aluguel",
            amount=Decimal("1000.00"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=date(2026, 1, 5),
            is_recurring=True,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 4, 5),
            currency="BRL",
        )
        db.session.add(template)
        db.session.commit()

        created_first = RecurrenceService.generate_missing_occurrences(
            reference_date=date(2026, 4, 30)
        )
        created_second = RecurrenceService.generate_missing_occurrences(
            reference_date=date(2026, 4, 30)
        )

        transactions = Transaction.query.filter_by(
            user_id=user.id, title="Aluguel", deleted=False
        ).order_by(Transaction.due_date.asc())
        due_dates = [item.due_date for item in transactions]

        assert created_first == 3
        assert created_second == 0
        assert due_dates == [
            date(2026, 1, 5),
            date(2026, 2, 5),
            date(2026, 3, 5),
            date(2026, 4, 5),
        ]


def test_generate_missing_occurrences_skips_invalid_or_installment(app) -> None:
    with app.app_context():
        user = _create_user()

        invalid_window = Transaction(
            user_id=user.id,
            title="Invalida",
            amount=Decimal("50.00"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=date(2026, 2, 10),
            is_recurring=True,
            start_date=date(2026, 3, 10),
            end_date=date(2026, 2, 10),
            currency="BRL",
        )
        recurring_installment = Transaction(
            user_id=user.id,
            title="Parcelada recorrente",
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=date(2026, 1, 15),
            is_recurring=True,
            is_installment=True,
            installment_count=2,
            start_date=date(2026, 1, 15),
            end_date=date(2026, 3, 15),
            currency="BRL",
        )
        db.session.add_all([invalid_window, recurring_installment])
        db.session.commit()

        created = RecurrenceService.generate_missing_occurrences(
            reference_date=date(2026, 3, 31)
        )

        assert created == 0
