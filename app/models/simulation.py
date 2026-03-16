# mypy: disable-error-code="name-defined"
"""Simulation model — J7 (salary_net, rescission, etc.)."""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class Simulation(db.Model):
    """A single tool-calculation run, optionally tied to a user and a goal."""

    __tablename__ = "simulations"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    # NULL ↔ anonymous simulation (never persisted after session)
    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True, index=True
    )
    tool_id = db.Column(db.String(60), nullable=False, index=True)
    rule_version = db.Column(db.String(20), nullable=False)
    inputs = db.Column(JSONB, nullable=False)
    result = db.Column(JSONB, nullable=False)
    saved = db.Column(db.Boolean, nullable=False, default=False)
    goal_id = db.Column(UUID(as_uuid=True), db.ForeignKey("goals.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)

    __table_args__ = (
        db.Index("ix_simulations_user_created", "user_id", "created_at"),
        db.Index("ix_simulations_user_saved", "user_id", "saved"),
    )

    def __repr__(self) -> str:
        return f"<Simulation tool={self.tool_id} user={self.user_id}>"
