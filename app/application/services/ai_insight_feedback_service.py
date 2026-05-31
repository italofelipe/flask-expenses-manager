"""Application service for AI insight feedback (#1387).

Persists per-user ratings (0–5 on relevance/truthfulness/depth/usefulness) plus a
free-text comment, and exposes an aggregate used to drive continuous improvement
of the insight prompts. One feedback row per (user, insight) — re-submitting
updates it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func

from app.extensions.database import db
from app.models.ai_insight import AIInsight
from app.models.ai_insight_feedback import FEEDBACK_RATING_FIELDS, AIInsightFeedback


@dataclass(frozen=True)
class AIInsightFeedbackError(Exception):
    message: str
    code: str
    status_code: int


def _serialize(feedback: AIInsightFeedback) -> dict[str, Any]:
    return {
        "id": str(feedback.id),
        "insight_id": str(feedback.insight_id),
        "relevance": feedback.relevance,
        "truthfulness": feedback.truthfulness,
        "depth": feedback.depth,
        "usefulness": feedback.usefulness,
        "comment": feedback.comment,
        "created_at": (
            feedback.created_at.isoformat() if feedback.created_at else None
        ),
        "updated_at": (
            feedback.updated_at.isoformat() if feedback.updated_at else None
        ),
    }


def submit_insight_feedback(
    *,
    user_id: UUID,
    insight_id: UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Create or update the feedback a user gives on one of their insights.

    Raises ``AIInsightFeedbackError`` (404) when the insight does not exist or
    does not belong to the user.
    """
    insight = db.session.get(AIInsight, insight_id)
    if insight is None or insight.user_id != user_id:
        raise AIInsightFeedbackError(
            message="Insight não encontrado.",
            code="AI_INSIGHT_NOT_FOUND",
            status_code=404,
        )

    feedback = AIInsightFeedback.query.filter_by(
        user_id=user_id, insight_id=insight_id
    ).first()
    if feedback is None:
        feedback = AIInsightFeedback(user_id=user_id, insight_id=insight_id)
        db.session.add(feedback)

    feedback.relevance = int(data["relevance"])
    feedback.truthfulness = int(data["truthfulness"])
    feedback.depth = int(data["depth"])
    feedback.usefulness = int(data["usefulness"])
    feedback.comment = data.get("comment")

    db.session.commit()
    return _serialize(feedback)


def get_insight_feedback_aggregate() -> dict[str, Any]:
    """Average rating per dimension across all feedback — input for prompt tuning."""
    columns = [
        func.avg(getattr(AIInsightFeedback, field)) for field in FEEDBACK_RATING_FIELDS
    ]
    row = db.session.query(func.count(AIInsightFeedback.id), *columns).one()
    total = int(row[0] or 0)
    averages = {
        field: (round(float(row[index + 1]), 2) if row[index + 1] is not None else None)
        for index, field in enumerate(FEEDBACK_RATING_FIELDS)
    }
    return {"total_feedback": total, "averages": averages}


__all__ = [
    "AIInsightFeedbackError",
    "submit_insight_feedback",
    "get_insight_feedback_aggregate",
]
