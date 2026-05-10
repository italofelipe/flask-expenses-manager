"""ai1 — create llm_audit_logs table

Revision ID: ai1
Revises: push1
Create Date: 2026-05-10

Stores every LLM call made on behalf of a user:
prompt, response, token usage, cost estimate, and latency.
No native enums — all string columns with CHECK constraints or plain text.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "ai1"
down_revision = "push1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(100), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("response_text", sa.Text, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost_usd",
            sa.Numeric(10, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_llm_audit_logs_user_id", "llm_audit_logs", ["user_id"])
    op.create_index("ix_llm_audit_logs_created_at", "llm_audit_logs", ["created_at"])
    op.create_index("ix_llm_audit_logs_endpoint", "llm_audit_logs", ["endpoint"])


def downgrade() -> None:
    op.drop_index("ix_llm_audit_logs_endpoint")
    op.drop_index("ix_llm_audit_logs_created_at")
    op.drop_index("ix_llm_audit_logs_user_id")
    op.drop_table("llm_audit_logs")
