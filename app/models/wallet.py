import uuid
from datetime import date

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db


class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(128), nullable=False)
    value = db.Column(db.Numeric(12, 2), nullable=False)

    estimated_value_on_create_date = db.Column(db.Numeric(12, 2), nullable=True)

    ticker = db.Column(db.String(16), nullable=True)
    quantity = db.Column(db.Integer, nullable=True)

    register_date = db.Column(db.Date, nullable=False)
    target_withdraw_date = db.Column(db.Date, nullable=True)
    should_be_on_wallet = db.Column(db.Boolean, nullable=False)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    # Relacionamento (opcional, útil para backref no User)
    user = db.relationship("User", backref="wallet_entries")

    def __repr__(self) -> str:
        return f"<Wallet {self.name} ({self.value})>"
