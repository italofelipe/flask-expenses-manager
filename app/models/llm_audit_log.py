# mypy: disable-error-code=name-defined

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class LLMAuditLog(db.Model):
    """Audit log for every LLM call made on behalf of a user.

    Stores prompt, response, token usage, cost estimate, and latency so that
    costs can be tracked, abuse detected, and model behaviour audited over time.
    """

    __tablename__ = "llm_audit_logs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Which advisory endpoint triggered this call.
    # Examples: "spending_insights", "goal_projection", "weekly_summary"
    endpoint = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    response_text = db.Column(db.Text, nullable=False)
    prompt_tokens = db.Column(db.Integer, nullable=False, default=0)
    completion_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    estimated_cost_usd = db.Column(db.Numeric(10, 8), nullable=False, default=0)
    latency_ms = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)

    __table_args__ = (
        db.Index("ix_llm_audit_logs_user_id", "user_id"),
        db.Index("ix_llm_audit_logs_created_at", "created_at"),
        db.Index("ix_llm_audit_logs_endpoint", "endpoint"),
    )

    def __repr__(self) -> str:
        return (
            f"<LLMAuditLog id={self.id} user_id={self.user_id} "
            f"endpoint={self.endpoint!r} model={self.model!r} "
            f"total_tokens={self.total_tokens}>"
        )
