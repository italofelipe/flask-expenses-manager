# mypy: disable-error-code=name-defined

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive

# Rating dimensions collected for each insight (0–5 scale).
FEEDBACK_RATING_FIELDS: tuple[str, ...] = (
    "relevance",
    "truthfulness",
    "depth",
    "usefulness",
)
FEEDBACK_RATING_MIN = 0
FEEDBACK_RATING_MAX = 5


class AIInsightFeedback(db.Model):
    """User rating + free-text feedback on a generated AI insight (#1387).

    Powers continuous improvement: the team reads aggregated scores per
    dimension/model to refine prompts. One row per (user, insight) — re-submitting
    updates the existing row.
    """

    __tablename__ = "ai_insight_feedback"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    insight_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("ai_insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    relevance = db.Column(db.Integer, nullable=False)
    truthfulness = db.Column(db.Integer, nullable=False)
    depth = db.Column(db.Integer, nullable=False)
    usefulness = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False
    )

    insight = db.relationship("AIInsight", backref="feedback_entries")

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "insight_id", name="uq_ai_insight_feedback_user_insight"
        ),
        db.Index("ix_ai_insight_feedback_insight_id", "insight_id"),
        db.Index("ix_ai_insight_feedback_user_id", "user_id"),
        db.CheckConstraint(
            "relevance BETWEEN 0 AND 5 AND truthfulness BETWEEN 0 AND 5 "
            "AND depth BETWEEN 0 AND 5 AND usefulness BETWEEN 0 AND 5",
            name="ck_ai_insight_feedback_rating_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AIInsightFeedback id={self.id} insight_id={self.insight_id} "
            f"user_id={self.user_id}>"
        )
