from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.email_provider import get_email_outbox


def test_dispatch_due_soon_sends_reminders(app) -> None:
    today = date(2030, 6, 15)
    with app.app_context():
        user = User(
            id=uuid.uuid4(),
            name="CLI Test User",
            email="cli-test@email.com",
            password="hash",
        )
        db.session.add(user)
        db.session.flush()

        tx_7 = Transaction(
            user_id=user.id,
            title="Aluguel",
            amount=Decimal("1500.00"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=today + timedelta(days=7),
        )
        tx_1 = Transaction(
            user_id=user.id,
            title="Internet",
            amount=Decimal("99.90"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=today + timedelta(days=1),
        )
        db.session.add_all([tx_7, tx_1])
        db.session.commit()

        runner = app.test_cli_runner()
        # Patch today so the CLI picks up the right window.
        # The service uses date.today() internally, so we monkeypatch it.
        import unittest.mock as mock

        with mock.patch(
            "app.application.services.transaction_reminder_service.date"
        ) as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = runner.invoke(args=["reminders", "dispatch-due-soon"])

        assert result.exit_code == 0
        assert "7-day reminders:" in result.output
        assert "1-day reminders:" in result.output
        assert "sent=1" in result.output

        outbox = get_email_outbox()
        assert len(outbox) >= 1


def test_dispatch_due_soon_dry_run_does_not_send(app) -> None:
    runner = app.test_cli_runner()
    result = runner.invoke(args=["reminders", "dispatch-due-soon", "--dry-run"])

    assert result.exit_code == 0
    assert "[dry-run]" in result.output

    outbox = get_email_outbox()
    assert len(outbox) == 0
