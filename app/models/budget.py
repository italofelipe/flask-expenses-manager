# mypy: disable-error-code=name-defined

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive

BUDGET_PERIODS = ("monthly", "weekly", "custom")


class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    tag_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("tags.id"), nullable=True
    )  # null = overall budget (no category)

    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    period = db.Column(
        db.String(20),
        nullable=False,
        default="monthly",
        server_default="monthly",
    )
    start_date = db.Column(db.Date, nullable=True)  # for "custom" period
    end_date = db.Column(db.Date, nullable=True)  # for "custom" period
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.text("true"),
    )

    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )

    tag = db.relationship("Tag", backref="budgets")

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_budgets_amount_positive"),
        db.CheckConstraint(
            "period IN ('monthly', 'weekly', 'custom')",
            name="ck_budgets_period_valid",
        ),
        db.Index("ix_budgets_user_id", "user_id"),
        db.Index("ix_budgets_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<Budget(id={self.id}, name={self.name!r}, "
            f"amount={self.amount}, period={self.period!r})>"
        )
