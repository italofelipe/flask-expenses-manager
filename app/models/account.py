# mypy: disable-error-code=name-defined

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db

ACCOUNT_TYPE_VALUES = ("checking", "savings", "investment", "wallet", "other")


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(
        db.String(20),
        nullable=False,
        default="checking",
        server_default="checking",
    )
    institution = db.Column(db.String(100), nullable=True)
    initial_balance = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
