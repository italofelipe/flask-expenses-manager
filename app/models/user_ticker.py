from uuid import uuid4

from app.extensions.database import db


class UserTicker(db.Model):
    __tablename__ = "user_tickers"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    symbol = db.Column(db.String, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    type = db.Column(db.String, nullable=True)  # Ex: 'stock', 'fii', etc.

    user_id = db.Column(
        db.Uuid(as_uuid=True), db.ForeignKey("users.id"), nullable=False
    )

    user = db.relationship("User", back_populates="tickers")
