# mypy: disable-error-code=name-defined

import enum
from datetime import datetime
from typing import Any
from uuid import UUID as UUIDType
from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db


class TransactionType(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionStatus(enum.Enum):
    PAID = "paid"
    PENDING = "pending"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    OVERDUE = "overdue"


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300))
    observation = db.Column(db.String(500))
    is_recurring = db.Column(db.Boolean, default=False)
    is_installment = db.Column(db.Boolean, default=False)
    installment_count = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="BRL")

    status = db.Column(db.Enum(TransactionStatus), default=TransactionStatus.PENDING)
    type = db.Column(db.Enum(TransactionType), nullable=False)

    due_date = db.Column(db.Date, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    tag_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tags.id"), nullable=True)
    account_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("accounts.id"), nullable=True
    )
    credit_card_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("credit_cards.id"), nullable=True
    )
    installment_group_id = db.Column(UUID(as_uuid=True), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)

    deleted = db.Column(
        db.Boolean, default=False, nullable=False, server_default=db.text("false")
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tag = db.relationship("Tag", backref="transactions")
    account = db.relationship("Account", backref="transactions")
    credit_card = db.relationship("CreditCard", backref="transactions")

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, title={self.title}, amount={self.amount}, "
            f"status={self.status})>"
        )

    @staticmethod
    def get_monthly_summary(user_id: UUIDType, year: int, month: int) -> dict[str, Any]:
        from sqlalchemy import extract, func

        income_total = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter_by(user_id=user_id, deleted=False, type=TransactionType.INCOME)
            .filter(extract("year", Transaction.due_date) == year)
            .filter(extract("month", Transaction.due_date) == month)
            .scalar()
        )

        expense_total = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter_by(user_id=user_id, deleted=False, type=TransactionType.EXPENSE)
            .filter(extract("year", Transaction.due_date) == year)
            .filter(extract("month", Transaction.due_date) == month)
            .scalar()
        )

        transactions = (
            Transaction.query.filter_by(user_id=user_id, deleted=False)
            .filter(extract("year", Transaction.due_date) == year)
            .filter(extract("month", Transaction.due_date) == month)
            .all()
        )

        return {
            "income_total": str(income_total),
            "expense_total": str(expense_total),
            "transactions": transactions,
        }
