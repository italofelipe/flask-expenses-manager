"""B8: Add user profile V1 fields + rename monthly_income to monthly_income_net

Revision ID: b8_add_user_profile_fields
Revises: c3f8d2a1b9e4
Create Date: 2026-02-22 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b8_add_user_profile_fields"
down_revision = "c3f8d2a1b9e4"
branch_labels = None
depends_on = None


def upgrade():
    # New profile fields
    op.add_column("users", sa.Column("state_uf", sa.String(length=2), nullable=True))
    op.add_column(
        "users", sa.Column("occupation", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "users", sa.Column("investor_profile", sa.String(length=32), nullable=True)
    )
    op.add_column("users", sa.Column("financial_objectives", sa.Text(), nullable=True))

    # Rename existing column for backward-compatible naming
    # (model exposes hybrid_property monthly_income -> monthly_income_net)
    op.alter_column(
        "users",
        "monthly_income",
        new_column_name="monthly_income_net",
    )


def downgrade():
    # Revert rename
    op.alter_column(
        "users",
        "monthly_income_net",
        new_column_name="monthly_income",
    )

    # Drop new profile fields (reverse order)
    op.drop_column("users", "financial_objectives")
    op.drop_column("users", "investor_profile")
    op.drop_column("users", "occupation")
    op.drop_column("users", "state_uf")
