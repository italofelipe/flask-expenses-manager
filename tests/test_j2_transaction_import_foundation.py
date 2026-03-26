from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User


def _create_user(*, suffix: str) -> User:
    user = User(name=f"user-{suffix}", email=f"user-{suffix}@email.com", password="x")
    db.session.add(user)
    db.session.flush()
    return user


def _create_transaction(*, user_id, external_id: str | None = None) -> Transaction:
    transaction = Transaction(
        user_id=user_id,
        title="Compra importada",
        amount=Decimal("42.90"),
        type=TransactionType.EXPENSE,
        due_date=date(2026, 3, 26),
        status=TransactionStatus.PENDING,
        external_id=external_id,
        bank_name="nubank",
    )
    db.session.add(transaction)
    return transaction


def test_transaction_source_defaults_to_manual(app) -> None:
    with app.app_context():
        user = _create_user(suffix="source-default")
        transaction = _create_transaction(user_id=user.id)

        db.session.commit()

        assert transaction.source == "manual"
        assert transaction.external_id is None
        assert transaction.bank_name == "nubank"


def test_transaction_external_id_is_unique_per_user(app) -> None:
    with app.app_context():
        user = _create_user(suffix="same-user")
        _create_transaction(user_id=user.id, external_id="OFX-001")
        db.session.commit()

        _create_transaction(user_id=user.id, external_id="OFX-001")
        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_transaction_external_id_allows_reuse_across_users(app) -> None:
    with app.app_context():
        first_user = _create_user(suffix="first")
        second_user = _create_user(suffix="second")

        _create_transaction(user_id=first_user.id, external_id="OFX-REUSED")
        _create_transaction(user_id=second_user.id, external_id="OFX-REUSED")

        db.session.commit()
