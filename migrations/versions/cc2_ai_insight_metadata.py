"""ai_insight_metadata_json

Adds a nullable Text JSON column on `ai_insights` to persist observability
metadata produced by the MVP-3 financial insight pipeline:

- snapshot_version (e.g. "financial_insight_snapshot.v1")
- comparisons_available (list of comparison-period keys present)
- dimensions_present (list of dimensions used by LLM items)
- snapshot_bytes_original / snapshot_bytes_final
- truncated (bool)

Legacy rows keep NULL — caller must handle absence.

Revision ID: cc2_ai_insight_metadata
Revises: cc1_credit_card_extension
Create Date: 2026-05-18 12:00:00.000000

Refs: #1289 (auraxis-api), Sprint 5 of MVP-3 wiki.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "cc2_ai_insight_metadata"
down_revision = "cc1_credit_card_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_insights",
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_insights", "metadata_json")
