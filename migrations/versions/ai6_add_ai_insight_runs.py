"""ai6 — create ai_insight_runs table

Revision ID: ai6_add_ai_insight_runs
Revises: cc2_ai_insight_metadata
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ai6_add_ai_insight_runs"
down_revision = "cc2_ai_insight_metadata"
branch_labels = None
depends_on = None


def _jsonb_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        "ai_insight_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ai_insight_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_insights.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            sa.CheckConstraint(
                "status IN ('previewed','generated','cached','rejected',"
                "'blocked','failed','purged')",
                name="ck_ai_insight_runs_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "period_type",
            sa.String(length=20),
            sa.CheckConstraint(
                "period_type IN ('daily','weekly','monthly','recap')",
                name="ck_ai_insight_runs_period_type",
            ),
            nullable=False,
        ),
        sa.Column("period_label", sa.String(length=30), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("snapshot_schema_version", sa.String(length=80), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=96), nullable=False),
        sa.Column("previous_snapshot_hash", sa.String(length=96), nullable=True),
        sa.Column("prompt_template_version", sa.String(length=80), nullable=False),
        _jsonb_column("snapshot_json"),
        _jsonb_column("evidence_manifest_json"),
        _jsonb_column("data_quality_json"),
        _jsonb_column("rejection_reasons_json"),
        _jsonb_column("truncation_flags_json"),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("purged_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_ai_insight_runs_user_id", "ai_insight_runs", ["user_id"])
    op.create_index(
        "ix_ai_insight_runs_ai_insight_id",
        "ai_insight_runs",
        ["ai_insight_id"],
    )
    op.create_index(
        "ix_ai_insight_runs_snapshot_hash",
        "ai_insight_runs",
        ["snapshot_hash"],
    )
    op.create_index(
        "ix_ai_insight_runs_expires",
        "ai_insight_runs",
        ["expires_at", "purged_at"],
    )
    op.create_index(
        "ix_ai_insight_runs_user_period",
        "ai_insight_runs",
        ["user_id", "period_type", "period_label"],
    )
    op.create_index("ix_ai_insight_runs_status", "ai_insight_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_insight_runs_status", table_name="ai_insight_runs")
    op.drop_index("ix_ai_insight_runs_user_period", table_name="ai_insight_runs")
    op.drop_index("ix_ai_insight_runs_expires", table_name="ai_insight_runs")
    op.drop_index("ix_ai_insight_runs_snapshot_hash", table_name="ai_insight_runs")
    op.drop_index("ix_ai_insight_runs_ai_insight_id", table_name="ai_insight_runs")
    op.drop_index("ix_ai_insight_runs_user_id", table_name="ai_insight_runs")
    op.drop_table("ai_insight_runs")
