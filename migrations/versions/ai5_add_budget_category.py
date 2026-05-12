"""Add category column to budgets (#1240).

Revision ID: ai5
Revises: ai4
Create Date: 2026-05-12

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ai5"
down_revision = "ai4"
branch_labels = None
depends_on = None

_VALID_CATEGORIES = (
    "alimentacao",
    "transporte",
    "moradia",
    "saude",
    "lazer",
    "educacao",
    "investimentos",
    "poupanca",
    "outros",
)


def upgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column(
            "category",
            sa.String(length=20),
            sa.CheckConstraint(
                f"category IN {_VALID_CATEGORIES!r} OR category IS NULL",
                name="ck_budgets_category",
            ),
            nullable=True,
        ),
    )
    # Populate category from linked tag name for existing budgets where tag
    # matches a known DEFAULT_TAGS name (case-insensitive, normalized to lower).
    op.execute(
        """
        UPDATE budgets
        SET category = LOWER(REPLACE(tags.name, 'ç', 'c'))
        FROM tags
        WHERE budgets.tag_id = tags.id
          AND LOWER(tags.name) IN (
            'alimentacao', 'alimentação',
            'transporte',
            'moradia',
            'saude', 'saúde',
            'lazer',
            'educacao', 'educação',
            'investimentos',
            'poupanca', 'poupança',
            'outros'
          )
        """
    )


def downgrade() -> None:
    op.drop_column("budgets", "category")
