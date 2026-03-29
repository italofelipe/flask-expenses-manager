"""align shared_entry enums with frontend contract (B2)

Rename SharedEntryStatus values:
  active  -> accepted
  revoked -> declined

Rename SplitType value:
  fixed -> custom

Revision ID: b2_align_shared_entry_enums
Revises: 4a2e1d7c9b0f
Create Date: 2026-03-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "b2_align_shared_entry_enums"
down_revision = "4a2e1d7c9b0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safe pattern for renaming enum values inside Alembic transactional DDL:
    #   1. Drop the column default (PostgreSQL tracks the default as depending
    #      on the enum type, so DROP TYPE fails if the default still exists)
    #   2. Cast column to VARCHAR (releases the enum type constraint)
    #   3. UPDATE rows with plain string literals (no enum constraint active)
    #   4. DROP the old enum type
    #   5. CREATE the new enum type with renamed values
    #   6. Cast the column back to the new enum type
    #   7. Restore the column default using the new type

    # ------------------------------------------------------------------ #
    # sharedentriesstatus: active -> accepted, revoked -> declined
    # j618 migration created status with server_default='pending'::sharedentriesstatus
    # ------------------------------------------------------------------ #
    op.execute("ALTER TABLE shared_entries ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE shared_entries ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("UPDATE shared_entries SET status = 'accepted' WHERE status = 'active'")
    op.execute("UPDATE shared_entries SET status = 'declined' WHERE status = 'revoked'")
    op.execute("DROP TYPE sharedentriesstatus")
    op.execute(
        "CREATE TYPE sharedentriesstatus AS ENUM ('pending', 'accepted', 'declined')"
    )
    op.execute(
        "ALTER TABLE shared_entries "
        "ALTER COLUMN status TYPE sharedentriesstatus "
        "USING status::sharedentriesstatus"
    )
    op.execute(
        "ALTER TABLE shared_entries "
        "ALTER COLUMN status SET DEFAULT 'pending'::sharedentriesstatus"
    )

    # ------------------------------------------------------------------ #
    # splittype: fixed -> custom
    # split_type has no server_default, so no default drop/restore needed
    # ------------------------------------------------------------------ #
    op.execute("ALTER TABLE shared_entries ALTER COLUMN split_type TYPE VARCHAR(20)")
    op.execute(
        "UPDATE shared_entries SET split_type = 'custom' WHERE split_type = 'fixed'"
    )
    op.execute("DROP TYPE splittype")
    op.execute("CREATE TYPE splittype AS ENUM ('equal', 'percentage', 'custom')")
    op.execute(
        "ALTER TABLE shared_entries "
        "ALTER COLUMN split_type TYPE splittype "
        "USING split_type::splittype"
    )


def downgrade() -> None:
    # splittype: custom -> fixed
    op.execute("ALTER TABLE shared_entries ALTER COLUMN split_type TYPE VARCHAR(20)")
    op.execute(
        "UPDATE shared_entries SET split_type = 'fixed' WHERE split_type = 'custom'"
    )
    op.execute("DROP TYPE splittype")
    op.execute("CREATE TYPE splittype AS ENUM ('equal', 'percentage', 'fixed')")
    op.execute(
        "ALTER TABLE shared_entries "
        "ALTER COLUMN split_type TYPE splittype "
        "USING split_type::splittype"
    )

    # sharedentriesstatus: accepted -> active, declined -> revoked
    op.execute("ALTER TABLE shared_entries ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE shared_entries ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("UPDATE shared_entries SET status = 'active' WHERE status = 'accepted'")
    op.execute("UPDATE shared_entries SET status = 'revoked' WHERE status = 'declined'")
    op.execute("DROP TYPE sharedentriesstatus")
    op.execute(
        "CREATE TYPE sharedentriesstatus AS ENUM ('pending', 'active', 'revoked')"
    )
    op.execute(
        "ALTER TABLE shared_entries "
        "ALTER COLUMN status TYPE sharedentriesstatus "
        "USING status::sharedentriesstatus"
    )
    op.execute(
        "ALTER TABLE shared_entries "
        "ALTER COLUMN status SET DEFAULT 'pending'::sharedentriesstatus"
    )
