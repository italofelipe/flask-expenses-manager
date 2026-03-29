from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.application.services.transaction_reminder_service import (
    dispatch_due_transaction_reminders,
)
from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.email_provider import get_email_outbox


def test_transaction_reminder_service_dispatches_due_soon_email(app) -> None:
    today = date(2026, 3, 29)
    with app.app_context():
        user = User(
            id=uuid.uuid4(),
            name="Auraxis User",
            email="alerts@email.com",
            password="hash",
        )
        db.session.add(user)
        db.session.flush()
        transaction = Transaction(
            user_id=user.id,
            title="Conta de energia",
            amount=Decimal("120.50"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=today + timedelta(days=7),
        )
        db.session.add(transaction)
        db.session.commit()

        result = dispatch_due_transaction_reminders(days_before_due=7, today=today)

        assert result.scanned == 1
        assert result.sent == 1
        outbox = get_email_outbox()
        assert len(outbox) == 1
        assert outbox[0]["email"] == "alerts@email.com"
        assert outbox[0]["tag"] == "due_soon_7_days"


def test_transaction_reminder_service_is_idempotent_per_day(app) -> None:
    today = date(2026, 3, 29)
    with app.app_context():
        user = User(
            id=uuid.uuid4(),
            name="Auraxis User",
            email="alerts@email.com",
            password="hash",
        )
        db.session.add(user)
        db.session.flush()
        transaction = Transaction(
            user_id=user.id,
            title="Conta de internet",
            amount=Decimal("99.90"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=today + timedelta(days=1),
        )
        db.session.add(transaction)
        db.session.commit()

        first = dispatch_due_transaction_reminders(days_before_due=1, today=today)
        second = dispatch_due_transaction_reminders(days_before_due=1, today=today)

        assert first.sent == 1
        assert second.sent == 0
        assert second.skipped == 1
