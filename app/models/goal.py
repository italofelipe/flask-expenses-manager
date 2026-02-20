# mypy: disable-error-code=name-defined

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class Goal(db.Model):
    __tablename__ = "goals"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(64), nullable=True)

    target_amount = db.Column(db.Numeric(12, 2), nullable=False)
    current_amount = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    priority = db.Column(db.Integer, nullable=False, default=3, server_default="3")
    target_date = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.String(24),
        nullable=False,
        default="active",
        server_default="active",
    )

    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )

    __table_args__ = (
        db.CheckConstraint("target_amount >= 0", name="ck_goals_target_amount_nonneg"),
        db.CheckConstraint(
            "current_amount >= 0",
            name="ck_goals_current_amount_nonneg",
        ),
        db.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_goals_priority"),
    )

    def __repr__(self) -> str:
        return (
            f"<Goal id={self.id} title={self.title!r} "
            f"target_amount={self.target_amount} status={self.status!r}>"
        )
