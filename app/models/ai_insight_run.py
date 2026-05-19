# mypy: disable-error-code=name-defined

from __future__ import annotations

import enum
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.models.ai_insight import InsightType
from app.utils.datetime_utils import utc_now_naive

DEFAULT_AI_INSIGHT_RUN_RETENTION_DAYS = 30


def _enum_values(e: type[enum.Enum]) -> list[str]:
    return [m.value for m in e]


def _default_expires_at() -> datetime:
    return utc_now_naive() + timedelta(days=DEFAULT_AI_INSIGHT_RUN_RETENTION_DAYS)


class AIInsightRunStatus(enum.Enum):
    """Lifecycle state for an auditable AI insight execution run."""

    previewed = "previewed"
    generated = "generated"
    cached = "cached"
    rejected = "rejected"
    blocked = "blocked"
    failed = "failed"
    purged = "purged"


class AIInsightRun(db.Model):
    """Auditable execution record for an AI Insight.

    ``AIInsight`` remains the display store and ``LLMAuditLog`` remains the
    token/cost call ledger. This model keeps the sanitized snapshot and evidence
    manifest needed to audit which deterministic facts supported a given run.
    """

    __tablename__ = "ai_insight_runs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_insight_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("ai_insights.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = db.Column(
        db.Enum(
            AIInsightRunStatus,
            name="ai_insight_run_status_enum",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=AIInsightRunStatus.previewed,
    )
    period_type = db.Column(
        db.Enum(
            InsightType,
            name="ai_insight_run_period_type_enum",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    period_label = db.Column(db.String(30), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    snapshot_schema_version = db.Column(db.String(80), nullable=False)
    snapshot_hash = db.Column(db.String(96), nullable=False)
    previous_snapshot_hash = db.Column(db.String(96), nullable=True)
    prompt_template_version = db.Column(db.String(80), nullable=False)
    snapshot_json = db.Column(db.JSON, nullable=True)
    evidence_manifest_json = db.Column(db.JSON, nullable=True)
    data_quality_json = db.Column(db.JSON, nullable=True)
    rejection_reasons_json = db.Column(db.JSON, nullable=True, default=list)
    truncation_flags_json = db.Column(db.JSON, nullable=True, default=dict)
    model = db.Column(db.String(80), nullable=True)
    tokens_in = db.Column(db.Integer, nullable=False, default=0)
    tokens_out = db.Column(db.Integer, nullable=False, default=0)
    tokens_total = db.Column(db.Integer, nullable=False, default=0)
    cost_usd = db.Column(db.Numeric(10, 8), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    expires_at = db.Column(db.DateTime, default=_default_expires_at, nullable=False)
    purged_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index("ix_ai_insight_runs_user_id", "user_id"),
        db.Index("ix_ai_insight_runs_ai_insight_id", "ai_insight_id"),
        db.Index("ix_ai_insight_runs_snapshot_hash", "snapshot_hash"),
        db.Index("ix_ai_insight_runs_expires", "expires_at", "purged_at"),
        db.Index(
            "ix_ai_insight_runs_user_period",
            "user_id",
            "period_type",
            "period_label",
        ),
        db.Index("ix_ai_insight_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIInsightRun id={self.id} user_id={self.user_id} "
            f"status={self.status.value!r} period={self.period_label!r} "
            f"snapshot_hash={self.snapshot_hash!r}>"
        )


__all__ = [
    "AIInsightRun",
    "AIInsightRunStatus",
    "DEFAULT_AI_INSIGHT_RUN_RETENTION_DAYS",
]
