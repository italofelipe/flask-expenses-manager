# mypy: disable-error-code=name-defined

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db

CREDIT_CARD_BRAND_VALUES = ("visa", "mastercard", "elo", "hipercard", "amex", "other")


class CreditCard(db.Model):
    __tablename__ = "credit_cards"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(20), nullable=True)
    limit_amount = db.Column(db.Numeric(12, 2), nullable=True)
    closing_day = db.Column(db.Integer, nullable=True)
    due_day = db.Column(db.Integer, nullable=True)
    last_four_digits = db.Column(db.String(4), nullable=True)
