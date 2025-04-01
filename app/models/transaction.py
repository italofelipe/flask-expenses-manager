import enum
from datetime import datetime
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
    tag_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tags.id"), nullable=True)
    account_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("accounts.id"), nullable=True
    )
    credit_card_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("credit_cards.id"), nullable=True
    )

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
