# mypy: disable-error-code=name-defined

import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db


class InvestmentOperation(db.Model):
    __tablename__ = "investment_operations"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("wallets.id"), nullable=False
    )
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)

    operation_type = db.Column(db.String(8), nullable=False)  # buy | sell
    quantity = db.Column(db.Numeric(18, 6), nullable=False)
    unit_price = db.Column(db.Numeric(18, 6), nullable=False)
    fees = db.Column(db.Numeric(12, 2), nullable=False, server_default="0")
    executed_at = db.Column(db.Date, nullable=False)
    notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    wallet = db.relationship("Wallet", backref="operations")
    user = db.relationship("User", backref="investment_operations")

    def __repr__(self) -> str:
        return (
            f"<InvestmentOperation "
            f"{self.operation_type} {self.quantity}@{self.unit_price}>"
        )
