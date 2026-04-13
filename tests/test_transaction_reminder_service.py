"""Tests for transaction_reminder_service.

Covers:
- Integration tests for dispatch happy path and idempotency
- Unit tests targeting missed branches (lines 61-62, 83, 100-101, 103-104,
  108-109) to bring coverage to >= 90 %.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.transaction_reminder_service import (
    _serialize_amount,
    dispatch_due_transaction_reminders,
)
from app.extensions.database import db
from app.models.alert import Alert, AlertStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.email_provider import get_email_outbox

# ---------------------------------------------------------------------------
# Integration tests — happy path + idempotency
# ---------------------------------------------------------------------------


def test_transaction_reminder_service_dispatches_due_soon_email(app) -> None:
    today = date(2030, 6, 15)
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
    today = date(2030, 6, 15)
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


# ---------------------------------------------------------------------------
# _serialize_amount — private helper
# ---------------------------------------------------------------------------


class TestSerializeAmount:
    def test_decimal_value_formatted_correctly(self) -> None:
        assert _serialize_amount(Decimal("1500.00")) == "1500.00"

    def test_float_value_formatted_correctly(self) -> None:
        assert _serialize_amount(99.9) == "99.90"

    def test_fallback_on_non_numeric_object(self) -> None:
        """Lines 61-62: exception branch returns str(value) instead of raising."""

        class BadDecimal:
            def __str__(self) -> str:
                return "not-a-number"

        result = _serialize_amount(BadDecimal())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# dispatch_due_transaction_reminders — branch coverage
# ---------------------------------------------------------------------------


class TestDispatchDueTransactionReminders:
    def test_unsupported_window_raises_value_error(self, app) -> None:
        """Line 83: days_before_due not in _REMINDER_WINDOWS -> ValueError."""
        with app.app_context():
            with pytest.raises(ValueError, match="Unsupported reminder window"):
                dispatch_due_transaction_reminders(days_before_due=5)

    def test_existing_alert_causes_skip(self, app) -> None:
        """Lines 100-101: transaction already has an alert for today -> skipped."""
        today = date(2030, 8, 1)
        with app.app_context():
            user = User(
                id=uuid.uuid4(),
                name="Skip Alert User",
                email="skip-alert@test.com",
                password="hash",
            )
            db.session.add(user)
            db.session.flush()

            tx = Transaction(
                user_id=user.id,
                title="Aluguel",
                amount=Decimal("1000.00"),
                type=TransactionType.EXPENSE,
                status=TransactionStatus.PENDING,
                due_date=today + timedelta(days=7),
            )
            db.session.add(tx)
            db.session.flush()

            existing = Alert(
                user_id=user.id,
                category="due_soon_7_days",
                status=AlertStatus.SENT,
                entity_type="transaction",
                entity_id=tx.id,
                triggered_at=datetime.combine(today, datetime.min.time()),
            )
            db.session.add(existing)
            db.session.commit()

            result = dispatch_due_transaction_reminders(days_before_due=7, today=today)

        assert result.scanned == 1
        assert result.skipped == 1
        assert result.sent == 0

    def test_dispatch_not_allowed_causes_skip(self, app) -> None:
        """Lines 103-104: _is_dispatch_allowed returns False -> skipped."""
        import unittest.mock as mock

        today = date(2030, 8, 1)
        with app.app_context():
            user = User(
                id=uuid.uuid4(),
                name="No Dispatch User",
                email="no-dispatch@test.com",
                password="hash",
            )
            db.session.add(user)
            db.session.flush()

            tx = Transaction(
                user_id=user.id,
                title="Internet",
                amount=Decimal("99.90"),
                type=TransactionType.EXPENSE,
                status=TransactionStatus.PENDING,
                due_date=today + timedelta(days=7),
            )
            db.session.add(tx)
            db.session.commit()

            with mock.patch(
                "app.application.services.transaction_reminder_service._is_dispatch_allowed",
                return_value=False,
            ):
                result = dispatch_due_transaction_reminders(
                    days_before_due=7, today=today
                )

        assert result.scanned == 1
        assert result.skipped == 1
        assert result.sent == 0

    def test_missing_user_causes_skip(self, app) -> None:
        """Lines 108-109: transaction.user_id has no matching User -> skipped."""
        import unittest.mock as mock

        today = date(2030, 8, 1)
        orphan_user_id = uuid.uuid4()

        with app.app_context():
            # SQLite does not enforce FK constraints by default
            tx = Transaction(
                user_id=orphan_user_id,
                title="Orphan tx",
                amount=Decimal("50.00"),
                type=TransactionType.EXPENSE,
                status=TransactionStatus.PENDING,
                due_date=today + timedelta(days=7),
            )
            db.session.add(tx)
            db.session.commit()

            with mock.patch(
                "app.application.services.transaction_reminder_service._is_dispatch_allowed",
                return_value=True,
            ):
                result = dispatch_due_transaction_reminders(
                    days_before_due=7, today=today
                )

        assert result.scanned == 1
        assert result.skipped == 1
        assert result.sent == 0
