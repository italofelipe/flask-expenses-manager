"""align shared_entry enums with frontend contract (B2)

Rename SharedEntryStatus values:
  active  -> accepted
  revoked -> declined

Rename SplitType value:
  fixed -> custom

Revision ID: b2_align_shared_entry_enums
Revises: j618_foundation
Create Date: 2026-03-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "b2_align_shared_entry_enums"
down_revision = "j618_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL does not support removing values from an enum type directly.
    # The safest strategy is:
    #   1. Add the new value to the type (ALTER TYPE … ADD VALUE is safe in PG ≥ 9.1)
    #   2. UPDATE the column to map old → new
    #   3. Drop the old values by recreating the type under a temporary name
    #
    # We use a raw DDL approach because SQLAlchemy/Alembic has no high-level
    # helper for renaming enum values on PostgreSQL.

    # ------------------------------------------------------------------ #
    # sharedentriesstatus: active -> accepted, revoked -> declined
    # ------------------------------------------------------------------ #
    op.execute("ALTER TYPE sharedentriesstatus ADD VALUE IF NOT EXISTS 'accepted'")
    op.execute("ALTER TYPE sharedentriesstatus ADD VALUE IF NOT EXISTS 'declined'")

    # Migrate existing data
    op.execute(
        "UPDATE shared_entries SET status = 'accepted' WHERE status = 'active'"
    )
    op.execute(
        "UPDATE shared_entries SET status = 'declined' WHERE status = 'revoked'"
    )

    # Recreate the type without the old values
    op.execute(
        """
        ALTER TABLE shared_entries
            ALTER COLUMN status TYPE VARCHAR(20)
        """
    )
    op.execute("DROP TYPE sharedentriesstatus")
    op.execute(
        "CREATE TYPE sharedentriesstatus AS ENUM ('pending', 'accepted', 'declined')"
    )
    op.execute(
        """
        ALTER TABLE shared_entries
            ALTER COLUMN status TYPE sharedentriesstatus
            USING status::sharedentriesstatus
        """
    )

    # ------------------------------------------------------------------ #
    # splittype: fixed -> custom
    # ------------------------------------------------------------------ #
    op.execute("ALTER TYPE splittype ADD VALUE IF NOT EXISTS 'custom'")

    op.execute("UPDATE shared_entries SET split_type = 'custom' WHERE split_type = 'fixed'")

    op.execute(
        """
        ALTER TABLE shared_entries
            ALTER COLUMN split_type TYPE VARCHAR(20)
        """
    )
    op.execute("DROP TYPE splittype")
    op.execute("CREATE TYPE splittype AS ENUM ('equal', 'percentage', 'custom')")
    op.execute(
        """
        ALTER TABLE shared_entries
            ALTER COLUMN split_type TYPE splittype
            USING split_type::splittype
        """
    )


def downgrade() -> None:
    # Reverse: custom -> fixed, accepted -> active, declined -> revoked

    # splittype
    op.execute("ALTER TYPE splittype ADD VALUE IF NOT EXISTS 'fixed'")
    op.execute("UPDATE shared_entries SET split_type = 'fixed' WHERE split_type = 'custom'")
    op.execute(
        "ALTER TABLE shared_entries ALTER COLUMN split_type TYPE VARCHAR(20)"
    )
    op.execute("DROP TYPE splittype")
    op.execute("CREATE TYPE splittype AS ENUM ('equal', 'percentage', 'fixed')")
    op.execute(
        "ALTER TABLE shared_entries ALTER COLUMN split_type TYPE splittype USING split_type::splittype"
    )

    # sharedentriesstatus
    op.execute("ALTER TYPE sharedentriesstatus ADD VALUE IF NOT EXISTS 'active'")
    op.execute("ALTER TYPE sharedentriesstatus ADD VALUE IF NOT EXISTS 'revoked'")
    op.execute(
        "UPDATE shared_entries SET status = 'active' WHERE status = 'accepted'"
    )
    op.execute(
        "UPDATE shared_entries SET status = 'revoked' WHERE status = 'declined'"
    )
    op.execute(
        "ALTER TABLE shared_entries ALTER COLUMN status TYPE VARCHAR(20)"
    )
    op.execute("DROP TYPE sharedentriesstatus")
    op.execute(
        "CREATE TYPE sharedentriesstatus AS ENUM ('pending', 'active', 'revoked')"
    )
    op.execute(
        "ALTER TABLE shared_entries ALTER COLUMN status TYPE sharedentriesstatus USING status::sharedentriesstatus"
    )
